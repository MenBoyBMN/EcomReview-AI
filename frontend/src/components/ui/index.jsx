import React, { useEffect, useState } from 'react';
import { Info, ChevronDown, X } from 'lucide-react';

export function Card({ children, className = '', padding = 'p-5', ...props }) {
  return (
    <div
      className={`min-w-0 bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl shadow-card ${padding} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function SectionHeader({ title, subtitle, icon: Icon, actions, className = '' }) {
  return (
    <div className={`flex items-start justify-between gap-4 flex-wrap mb-4 ${className}`}>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="w-5 h-5 text-indigo-600 dark:text-indigo-400 shrink-0" />}
          <h2 className="text-base font-semibold text-slate-900 dark:text-white leading-snug">
            {title}
          </h2>
        </div>
        {subtitle && (
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2 leading-relaxed">
            {subtitle}
          </p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2 flex-wrap shrink-0">{actions}</div>}
    </div>
  );
}

const BUTTON_VARIANTS = {
  primary:
    'bg-indigo-600 text-white hover:bg-indigo-500 shadow-sm shadow-indigo-500/15 border border-transparent',
  secondary:
    'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/80',
  success:
    'bg-emerald-600 text-white hover:bg-emerald-500 shadow-sm shadow-emerald-500/15 border border-transparent',
  danger:
    'bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800 hover:bg-rose-100 dark:hover:bg-rose-900/60',
  ghost:
    'bg-transparent text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-transparent',
};

const BUTTON_SIZES = {
  sm: 'h-8 px-3 text-xs rounded-lg',
  md: 'h-9 px-3.5 text-xs sm:text-sm rounded-xl',
};

export function Button({
  children,
  variant = 'secondary',
  size = 'md',
  className = '',
  type = 'button',
  ...props
}) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-1.5 whitespace-nowrap shrink-0 font-semibold transition-colors disabled:opacity-50 disabled:pointer-events-none ${
        BUTTON_SIZES[size] || BUTTON_SIZES.md
      } ${BUTTON_VARIANTS[variant] || BUTTON_VARIANTS.secondary} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

const BADGE_TONES = {
  neutral:
    'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
  info:
    'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/60 dark:text-indigo-300 dark:border-indigo-800/70',
  success:
    'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800/70',
  warning:
    'bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800/70',
  danger:
    'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800/70',
  purple:
    'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/60 dark:text-purple-300 dark:border-purple-800/70',
};

export function Badge({ children, tone = 'neutral', className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap shrink-0 px-2.5 py-0.5 rounded-full text-xs font-medium border ${
        BADGE_TONES[tone] || BADGE_TONES.neutral
      } ${className}`}
    >
      {children}
    </span>
  );
}

export function InfoTip({ text, children }) {
  if (!text) return children || null;
  return (
    <span className="relative inline-flex items-center group">
      {children || (
        <span className="inline-flex items-center justify-center w-4 h-4 rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-help">
          <Info className="w-3.5 h-3.5" />
        </span>
      )}
      <span className="pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-150 absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-60 p-2.5 rounded-xl bg-slate-900 dark:bg-slate-800 text-white text-xs font-normal leading-relaxed shadow-lg z-40 border border-slate-700">
        {text}
      </span>
    </span>
  );
}

export function StatCard({
  label,
  value,
  unit,
  subtext,
  tooltip,
  icon: Icon,
  tone = 'indigo',
  footer,
}) {
  const iconColors = {
    indigo: 'bg-indigo-50 text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-400',
    emerald: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400',
    rose: 'bg-rose-50 text-rose-600 dark:bg-rose-950/60 dark:text-rose-400',
    amber: 'bg-amber-50 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400',
  };

  const valueColors = {
    indigo: 'text-slate-900 dark:text-white',
    emerald: 'text-slate-900 dark:text-white',
    rose: 'text-rose-600 dark:text-rose-400',
    amber: 'text-amber-600 dark:text-amber-400',
  };

  return (
    <Card className="flex flex-col justify-between gap-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-sm font-medium text-slate-600 dark:text-slate-300 truncate">
            {label}
          </span>
          {tooltip && <InfoTip text={tooltip} />}
        </div>
        {Icon && (
          <div
            className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${
              iconColors[tone] || iconColors.indigo
            }`}
          >
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      <div>
        <div className="flex items-baseline gap-1.5">
          <span
            className={`text-3xl font-bold tabular-nums tracking-tight ${
              valueColors[tone] || valueColors.indigo
            }`}
          >
            {value}
          </span>
          {unit && <span className="text-sm font-medium text-slate-500">{unit}</span>}
        </div>
        {subtext && (
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 truncate">{subtext}</p>
        )}
      </div>

      {footer && (
        <div className="pt-2.5 border-t border-slate-100 dark:border-slate-800/80 text-xs">
          {footer}
        </div>
      )}
    </Card>
  );
}

export function Segmented({ options, value, onChange, className = '' }) {
  return (
    <div
      className={`inline-flex items-center flex-wrap gap-1 p-1 rounded-xl bg-slate-100 dark:bg-slate-800/90 border border-slate-200/70 dark:border-slate-700/60 ${className}`}
    >
      {options.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={String(opt.value)}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`inline-flex items-center gap-1.5 whitespace-nowrap shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              active
                ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            {opt.icon && <opt.icon className="w-3.5 h-3.5" />}
            <span>{opt.label}</span>
            {opt.count !== undefined && (
              <span
                className={`px-1.5 py-0.5 rounded-full text-xs tabular-nums ${
                  active
                    ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300'
                    : 'bg-slate-200/70 dark:bg-slate-700 text-slate-600 dark:text-slate-300'
                }`}
              >
                {opt.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="py-10 px-4 text-center flex flex-col items-center justify-center gap-2">
      {Icon && (
        <div className="w-10 h-10 rounded-2xl bg-slate-100 dark:bg-slate-800 text-slate-400 flex items-center justify-center mb-1">
          <Icon className="w-5 h-5" />
        </div>
      )}
      <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">{title}</div>
      {description && (
        <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md leading-relaxed">
          {description}
        </p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function Collapsible({ title, badge, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-4 py-2.5 flex items-center justify-between gap-2 text-left text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100/70 dark:hover:bg-slate-800/70 transition"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="truncate">{title}</span>
          {badge}
        </div>
        <ChevronDown
          className={`w-4 h-4 text-slate-400 shrink-0 transition-transform ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>
      {open && (
        <div className="px-4 pb-3.5 pt-2 border-t border-slate-200/60 dark:border-slate-800 text-xs">
          {children}
        </div>
      )}
    </div>
  );
}

export function Modal({ isOpen, onClose, title, subtitle, icon: Icon, children, footer, maxWidth = 'max-w-2xl' }) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm animate-fade-in"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className={`w-full ${maxWidth} max-h-[85vh] flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl overflow-hidden`}
      >
        <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800 flex items-start justify-between gap-3 bg-slate-50/70 dark:bg-slate-900/50">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              {Icon && <Icon className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0" />}
              <h3 className="text-sm font-bold text-slate-900 dark:text-white truncate">{title}</h3>
            </div>
            {subtitle && (
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 line-clamp-1">
                {subtitle}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800 shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto flex-1 space-y-4">{children}</div>

        {footer && (
          <div className="px-5 py-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/50 flex items-center justify-between gap-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

// CreBy: MenBoyBMN

