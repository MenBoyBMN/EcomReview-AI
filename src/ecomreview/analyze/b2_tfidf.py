"""Baseline 2 (B2): TF-IDF + Logistic Regression ABSA Pipeline.

Implements a Two-Tier training architecture:
- Tier 1: Overall Sentiment & Macro-Aspects trained on public benchmark (UIT-ViSFD).
- Tier 2: 8 Fine-grained Raincoat Aspects wrapped with SafeAspectClassifier,
  trained on shop dev data with deterministic rule fallback for rare classes.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from ecomreview.analyze.b1_rule import ASPECT_LEXICON, B1RuleAnalyzer
from ecomreview.normalize import normalize_social_text
from ecomreview.schemas import (
    Aspect,
    AspectOpinion,
    MacroAspect,
    Polarity,
    ReviewAnalysis,
)


@lru_cache(maxsize=8192)
def tokenize_vietnamese(text: str, enable_norm: bool = True) -> str:
    """Tokenize Vietnamese text using underthesea with fallback to whitespace."""
    norm = normalize_social_text(text, enable=enable_norm)
    try:
        import underthesea

        return str(underthesea.word_tokenize(norm, format="text"))
    except Exception:
        return norm


class SafeAspectClassifier:
    """Safe wrapper for aspect polarity classification with fallback on rare classes."""

    def __init__(self, aspect_name: str, random_state: int = 42):
        self.aspect_name = aspect_name
        self.random_state = random_state
        self.clf: LogisticRegression | None = None
        self.constant_label: str | None = None
        self.use_rule_fallback: bool = False

    def fit(self, X: Any, y: Sequence[str]) -> "SafeAspectClassifier":
        """Train classifier or configure fallback if unique classes < 2."""
        y_arr = np.asarray(y)
        unique_classes, counts = np.unique(y_arr, return_counts=True)

        # Classes must have at least 2 samples to fit LogisticRegression safely
        valid_classes = [cls for cls, cnt in zip(unique_classes, counts) if cnt >= 2]

        if len(valid_classes) >= 2:
            self.clf = LogisticRegression(
                C=1.0,
                max_iter=1000,
                class_weight="balanced",
                random_state=self.random_state,
            )
            self.clf.fit(X, y_arr)
            self.use_rule_fallback = False
        elif len(unique_classes) == 1:
            self.constant_label = str(unique_classes[0])
            self.clf = None
            self.use_rule_fallback = False
        else:
            # Not enough balanced samples across multiple classes
            self.clf = None
            self.use_rule_fallback = True

        return self

    def predict(self, X: Any) -> list[str]:
        """Predict aspect polarity labels."""
        if self.clf is not None:
            return list(self.clf.predict(X))
        if self.constant_label is not None:
            n_samples = X.shape[0] if hasattr(X, "shape") else len(X)
            return [self.constant_label] * n_samples
        # Fallback to none if rule fallback enabled
        n_samples = X.shape[0] if hasattr(X, "shape") else len(X)
        return ["none"] * n_samples


class B2TfidfAnalyzer:
    """Two-Tier TF-IDF + Logistic Regression ABSA Analyzer."""

    def __init__(self, random_state: int = 42, enable_norm: bool = True):
        self.random_state = random_state
        self.enable_norm = enable_norm
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=10000,
            sublinear_tf=True,
        )
        self.overall_clf: LogisticRegression | None = None
        self.macro_clfs: dict[str, SafeAspectClassifier] = {}
        self.fine_clfs: dict[str, SafeAspectClassifier] = {}
        self.rule_fallback = B1RuleAnalyzer(enable_norm=enable_norm)
        self.is_fitted: bool = False

    def _extract_evidence_for_aspect(self, text: str, aspect: Aspect) -> str:
        """Find matching domain keyword in text for evidence quote fidelity."""
        keywords = ASPECT_LEXICON.get(aspect, [])
        text_lower = text.lower()
        for kw in keywords:
            if kw in text_lower:
                return kw
        tokens = text.split()
        return " ".join(tokens[:5]) if tokens else "sản phẩm"

    def fit(
        self,
        public_train_path: str | Path,
        gold_dev_path: str | Path,
    ) -> "B2TfidfAnalyzer":
        """Fit Two-Tier pipeline on public benchmark and raincoat dev data."""
        public_texts: list[str] = []
        public_overall: list[str] = []
        public_macro_maps: list[dict[str, str]] = []

        with open(public_train_path, "r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                public_texts.append(tokenize_vietnamese(item["text"], enable_norm=self.enable_norm))
                public_overall.append(str(item.get("overall_sentiment", "neutral")).lower())
                m_map = {}
                for op in item.get("opinions", []):
                    m_map[op["aspect"]] = op["polarity"].lower()
                public_macro_maps.append(m_map)

        gold_texts: list[str] = []
        gold_fine_maps: list[dict[str, str]] = []

        with open(gold_dev_path, "r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                gold_texts.append(tokenize_vietnamese(item["text"], enable_norm=self.enable_norm))
                f_map = {}
                for op in item.get("opinions", []):
                    asp_val = (
                        op["aspect"].value if hasattr(op["aspect"], "value") else str(op["aspect"])
                    )
                    pol_val = (
                        op["polarity"].value
                        if hasattr(op["polarity"], "value")
                        else str(op["polarity"])
                    )
                    f_map[asp_val] = pol_val.lower()
                gold_fine_maps.append(f_map)

        # 1. Fit Vectorizer on combined corpus
        all_train_texts = public_texts + gold_texts
        self.vectorizer.fit(all_train_texts)

        X_public = self.vectorizer.transform(public_texts)
        X_gold = self.vectorizer.transform(gold_texts)

        # 2. Tier 1: Fit Overall Sentiment on public benchmark
        self.overall_clf = LogisticRegression(
            C=1.0,
            max_iter=1000,
            class_weight="balanced",
            random_state=self.random_state,
        )
        self.overall_clf.fit(X_public, public_overall)

        # 3. Tier 1: Fit 5 Macro Aspects on public benchmark
        for macro in MacroAspect:
            asp_str = macro.value
            y_macro = [m_map.get(asp_str, "none") for m_map in public_macro_maps]
            clf = SafeAspectClassifier(asp_str, random_state=self.random_state)
            clf.fit(X_public, y_macro)
            self.macro_clfs[asp_str] = clf

        # 4. Tier 2: Fit 8 Fine Raincoat Aspects on dev data
        for fine in Aspect:
            if fine == Aspect.GENERAL:
                continue
            asp_str = fine.value
            y_fine = [f_map.get(asp_str, "none") for f_map in gold_fine_maps]
            clf = SafeAspectClassifier(asp_str, random_state=self.random_state)
            clf.fit(X_gold, y_fine)
            self.fine_clfs[asp_str] = clf

        self.is_fitted = True
        return self

    def analyze_review(self, text: str, is_macro_track: bool = False) -> ReviewAnalysis:
        """Analyze a single review and return a ReviewAnalysis model."""
        if not self.is_fitted:
            raise RuntimeError("B2TfidfAnalyzer must be fitted or loaded before inference.")

        if not text or not text.strip():
            return ReviewAnalysis(
                overall_sentiment=Polarity.NEU,
                opinions=[],
                informative=False,
            )

        tokenized = tokenize_vietnamese(text, enable_norm=self.enable_norm)
        X = self.vectorizer.transform([tokenized])

        # Predict Overall Sentiment
        assert self.overall_clf is not None
        overall_pred = self.overall_clf.predict(X)[0]
        try:
            overall_pol = Polarity(overall_pred)
        except ValueError:
            overall_pol = Polarity.NEU

        opinions: list[AspectOpinion] = []

        if is_macro_track:
            for asp_str, clf in self.macro_clfs.items():
                pred_label = clf.predict(X)[0]
                if pred_label != "none":
                    try:
                        pol = Polarity(pred_label)
                        opinions.append(
                            AspectOpinion(
                                aspect=asp_str,  # Will be mapped via alias validator
                                polarity=pol,
                                evidence=text[:30],
                            )
                        )
                    except ValueError:
                        pass
        else:
            rule_analysis = self.rule_fallback.analyze_review(text)
            rule_map = {op.aspect.value: op for op in rule_analysis.opinions}

            for asp_enum in Aspect:
                if asp_enum == Aspect.GENERAL:
                    continue
                asp_str = asp_enum.value
                clf = self.fine_clfs.get(asp_str)
                if clf is None:
                    continue

                if clf.use_rule_fallback:
                    # Leverage rule fallback for aspects lacking enough train samples
                    if asp_str in rule_map:
                        opinions.append(rule_map[asp_str])
                else:
                    pred_label = clf.predict(X)[0]
                    if pred_label != "none":
                        try:
                            pol = Polarity(pred_label)
                            ev = self._extract_evidence_for_aspect(text, asp_enum)
                            opinions.append(
                                AspectOpinion(
                                    aspect=asp_enum,
                                    polarity=pol,
                                    evidence=ev,
                                )
                            )
                        except ValueError:
                            pass

        if not opinions:
            # Fallback to general opinion
            opinions.append(
                AspectOpinion(
                    aspect=Aspect.GENERAL,
                    polarity=overall_pol,
                    evidence=text[:30],
                )
            )

        informative = len(text.split()) >= 3

        return ReviewAnalysis(
            overall_sentiment=overall_pol,
            opinions=opinions,
            informative=informative,
        )

    def analyze_batch(
        self, texts: Sequence[str], is_macro_track: bool = False
    ) -> list[ReviewAnalysis]:
        """Analyze a list of review texts."""
        return [self.analyze_review(t, is_macro_track=is_macro_track) for t in texts]

    def save(self, filepath: str | Path) -> None:
        """Serialize fitted pipeline to disk using joblib."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, filepath: str | Path) -> "B2TfidfAnalyzer":
        """Load trained pipeline from disk."""
        return joblib.load(filepath)


# CreBy: MenBoyBMN
