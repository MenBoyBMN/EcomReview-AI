import React, { useEffect, useState } from 'react';
import { Users, Store, UserPlus, Shield, Lock, Unlock, PlusCircle } from 'lucide-react';
import { api } from '../api/client';
import { Modal, Button, Badge } from './ui';

export default function TeamManagementModal({
  isOpen,
  onClose,
  pilotShops = [],
  onWorkspaceChanged,
  showToast,
}) {
  const [activeSection, setActiveSection] = useState('staff');
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);

  // New CSKH staff form
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [selectedShops, setSelectedShops] = useState([]);
  const [creatingUser, setCreatingUser] = useState(false);

  // New Shop form
  const [shopName, setShopName] = useState('');
  const [shopSlug, setShopSlug] = useState('');
  const [industry, setIndustry] = useState('raincoat');
  const [industries, setIndustries] = useState([]);
  const [creatingShop, setCreatingShop] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      const [uRes, indRes] = await Promise.all([
        api.getTeamUsers(),
        api.getIndustries().catch(() => ({ industries: [] })),
      ]);
      setUsers(uRes?.users || []);
      setIndustries(indRes?.industries || []);
    } catch (err) {
      showToast?.(err.message || 'Không tải được danh sách nhân sự', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadData();
      if (pilotShops.length > 0) {
        setSelectedShops([pilotShops[0].slug]);
      }
    }
  }, [isOpen, pilotShops]);

  const toggleShop = (slug) => {
    setSelectedShops((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]
    );
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    if (selectedShops.length === 0) {
      showToast?.('Vui lòng chọn ít nhất 1 gian hàng cho nhân viên CSKH.', 'error');
      return;
    }
    try {
      setCreatingUser(true);
      await api.createTeamUser({
        email: email.trim(),
        full_name: fullName.trim() || email.trim(),
        password,
        role: 'cskh',
        allowed_shops: selectedShops,
      });
      setEmail('');
      setFullName('');
      setPassword('');
      showToast?.('Đã tạo tài khoản nhân viên CSKH thành công!', 'success');
      await loadData();
    } catch (err) {
      showToast?.(err.message || 'Không thể tạo nhân viên CSKH', 'error');
    } finally {
      setCreatingUser(false);
    }
  };

  const handleToggleUserStatus = async (user) => {
    try {
      await api.updateTeamUserStatus(user.id, !user.is_active);
      showToast?.(
        !user.is_active
          ? `Đã mở khóa tài khoản ${user.email}`
          : `Đã khóa tài khoản ${user.email} (mọi phiên đăng nhập cũ bị thu hồi)`,
        'info'
      );
      await loadData();
    } catch (err) {
      showToast?.(err.message || 'Không thể cập nhật trạng thái nhân viên', 'error');
    }
  };

  const handleCreateShop = async (e) => {
    e.preventDefault();
    const derivedSlug =
      shopSlug.trim() ||
      shopName
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9_-]+/g, '_')
        .replace(/^_+|_+$/g, '');
    try {
      setCreatingShop(true);
      await api.createWorkspaceShop({
        name: shopName.trim(),
        slug: derivedSlug,
        industry,
        platforms: ['shopee', 'tiktok'],
      });
      setShopName('');
      setShopSlug('');
      showToast?.('Đã thêm gian hàng mới vào hệ thống!', 'success');
      await onWorkspaceChanged?.();
      await loadData();
    } catch (err) {
      showToast?.(err.message || 'Không thể tạo gian hàng mới', 'error');
    } finally {
      setCreatingShop(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      icon={Users}
      title="Quản lý Đội ngũ CSKH & Gian hàng"
      subtitle="Phân quyền nhân viên CSKH theo từng gian hàng và mở thêm shop trong hạn mức gói"
      maxWidth="max-w-2xl"
    >
      <div className="space-y-4 text-sm">
        <div className="flex gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
          <button
            type="button"
            onClick={() => setActiveSection('staff')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 ${
              activeSection === 'staff'
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Nhân sự CSKH ({users.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveSection('shops')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 ${
              activeSection === 'shops'
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
            }`}
          >
            <Store className="w-3.5 h-3.5" />
            <span>Thêm gian hàng ({pilotShops.length})</span>
          </button>
        </div>

        {activeSection === 'staff' ? (
          <div className="space-y-4">
            <form
              onSubmit={handleCreateUser}
              className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-3"
            >
              <div className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
                <UserPlus className="w-3.5 h-3.5 text-indigo-600" />
                <span>Tạo tài khoản nhân viên CSKH mới</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="cskh@agency.vn"
                  className="h-9 px-3 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
                />
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Họ tên nhân viên"
                  className="h-9 px-3 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
                />
                <input
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Mật khẩu (>=6 ký tự)"
                  className="h-9 px-3 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
                />
              </div>
              <div>
                <div className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                  Phân quyền gian hàng được phép xử lý CSKH:
                </div>
                <div className="flex flex-wrap gap-2">
                  {pilotShops.map((s) => (
                    <label
                      key={s.slug}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-xs cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedShops.includes(s.slug)}
                        onChange={() => toggleShop(s.slug)}
                        className="rounded border-slate-300 text-indigo-600"
                      />
                      <span>{s.name}</span>
                    </label>
                  ))}
                </div>
              </div>
              <Button type="submit" variant="primary" size="sm" disabled={creatingUser}>
                <UserPlus className="w-3.5 h-3.5" />
                <span>{creatingUser ? 'Đang tạo...' : 'Cấp tài khoản CSKH'}</span>
              </Button>
            </form>

            <div className="space-y-2 max-h-60 overflow-y-auto">
              {loading ? (
                <div className="text-xs text-slate-400 py-4 text-center">Đang tải danh sách...</div>
              ) : (
                users.map((u) => (
                  <div
                    key={u.id}
                    className="flex items-center justify-between gap-3 p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-slate-900 dark:text-white truncate">
                          {u.full_name}
                        </span>
                        <Badge tone={u.role === 'owner' ? 'info' : 'neutral'}>
                          <Shield className="w-3 h-3 mr-1" />
                          {String(u.role).toUpperCase()}
                        </Badge>
                        <Badge tone={u.is_active ? 'success' : 'danger'}>
                          {u.is_active ? 'Hoạt động' : 'Đã khóa'}
                        </Badge>
                      </div>
                      <div className="text-[11px] text-slate-500 mt-0.5 truncate">
                        {u.email} • Shop: {(u.allowed_shops || []).join(', ') || '—'}
                      </div>
                    </div>
                    {u.role === 'cskh' && (
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => handleToggleUserStatus(u)}
                      >
                        {u.is_active ? (
                          <>
                            <Lock className="w-3.5 h-3.5 text-rose-500" />
                            <span>Khóa</span>
                          </>
                        ) : (
                          <>
                            <Unlock className="w-3.5 h-3.5 text-emerald-600" />
                            <span>Mở khóa</span>
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        ) : (
          <form
            onSubmit={handleCreateShop}
            className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-3"
          >
            <div className="text-xs font-bold text-slate-800 dark:text-slate-100">
              Thêm gian hàng mới vào Workspace
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                  Tên hiển thị gian hàng
                </label>
                <input
                  type="text"
                  required
                  value={shopName}
                  onChange={(e) => setShopName(e.target.value)}
                  placeholder="VD: Lumina Beauty Shopee Mall"
                  className="w-full h-9 px-3 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                  Mã Shop (Slug không dấu)
                </label>
                <input
                  type="text"
                  value={shopSlug}
                  onChange={(e) => setShopSlug(e.target.value)}
                  placeholder="vd: lumina_mall"
                  className="w-full h-9 px-3 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
                />
              </div>
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                Ngành hàng (Playbook AI)
              </label>
              <select
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="w-full h-9 px-3 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
              >
                {(industries.length > 0
                  ? industries
                  : [
                      { industry: 'raincoat', display_name: 'Áo mưa & Đồ đi mưa' },
                      { industry: 'fashion', display_name: 'Thời trang & May mặc' },
                      { industry: 'cosmetics', display_name: 'Mỹ phẩm & Chăm sóc da' },
                      { industry: 'home_living', display_name: 'Gia dụng & Đời sống' },
                      { industry: 'electronics', display_name: 'Phụ kiện & Điện tử' },
                    ]
                ).map((item) => (
                  <option key={item.industry} value={item.industry}>
                    {item.display_name}
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit" variant="primary" size="sm" disabled={creatingShop}>
              <PlusCircle className="w-3.5 h-3.5" />
              <span>{creatingShop ? 'Đang tạo...' : 'Tạo gian hàng'}</span>
            </Button>
          </form>
        )}
      </div>
    </Modal>
  );
}

// CreBy: MenBoyBMN
