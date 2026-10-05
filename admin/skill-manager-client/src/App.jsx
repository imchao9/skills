import { useEffect, useMemo, useState } from "react";
import {
  Activity, BookOpen, Check, ChevronDown, CircleHelp, Code2, Copy, FileCode2, FolderOpen,
  FolderTree, Grid2X2, HardDrive, Layers3, LayoutDashboard, List,
  Plus, RefreshCw, Search, Settings2, Tag, X, ShoppingCart, CheckSquare, BookmarkPlus, Trash2, Save,
} from "lucide-react";

const iconCycle = [FileCode2, Code2, BookOpen, FolderOpen, Layers3, FolderTree];
const iconTones = ["blue", "ink", "violet", "purple", "orange", "green"];

function IconBadge({ index = 0, size = 21 }) {
  const Icon = iconCycle[index % iconCycle.length];
  return <span className={`skill-icon skill-icon-${iconTones[index % iconTones.length]}`}><Icon size={size} strokeWidth={2.1} /></span>;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function SetsPage({ sets, skills, onUse, onDelete, onBack }) {
  const byId = new Map(skills.map((skill) => [skill.id, skill]));
  return <div className="sets-page">
    <div className="sets-page-heading"><div><div className="sets-eyebrow"><ShoppingCart size={15} /> Skill Sets</div><h1>Skill Sets</h1><p>把经常一起使用的 Skill 组合成可复用的工作集合。</p></div><button className="button button-secondary" onClick={onBack}><Layers3 size={14} /> 返回全部 Skills</button></div>
    {sets.length ? <div className="sets-table"><div className="sets-table-header"><span>Set</span><span>包含的 Skills</span><span>更新时间</span><span>操作</span></div>{sets.map((set, index) => { const members = set.skillIds.map((id) => byId.get(id)).filter(Boolean); return <article className="set-row" key={set.id}><div className="set-row-name"><span className={`set-index set-index-${index % 4}`}><Layers3 size={17} /></span><div><h2>{set.name}</h2><span>{members.length} 个 Skill</span></div></div><div className="set-row-members">{members.slice(0, 4).map((skill) => <span className="set-member" key={skill.id} title={skill.id}>{skill.name}</span>)}{members.length > 4 ? <span className="set-member set-member-more">+{members.length - 4}</span> : null}{!members.length ? <span className="set-member set-member-empty">成员已不存在</span> : null}</div><span className="set-row-date">{set.updatedAt ? new Date(set.updatedAt).toLocaleDateString("zh-CN") : "—"}</span><div className="set-row-actions"><button className="button button-secondary" onClick={() => onUse(set)}><List size={13} /> 查看成员</button><button className="icon-button" title="删除 Set" aria-label={`删除 ${set.name}`} onClick={() => onDelete(set)}><Trash2 size={15} /></button></div></article>; })}</div> : <div className="sets-empty-page"><ShoppingCart size={26} /><strong>还没有 Skill Set</strong><span>在全部 Skills 中勾选几项，然后点击“加入 Set”。</span><button className="button button-primary" onClick={onBack}><Plus size={14} /> 去选择 Skill</button></div>}
  </div>;
}

function FactoryPage({ factory, loading, busy, onCheck, onRefresh }) {
  if (loading && !factory) return <div className="factory-page"><div className="factory-empty">正在读取 software-factory 组合…</div></div>;
  if (!factory?.available) return <div className="factory-page"><div className="factory-heading"><div><div className="factory-eyebrow"><FolderTree size={15} /> SOFTWARE FACTORY</div><h1>Software Factory</h1><p>{factory?.error || "没有找到组合 profile。"}</p></div></div></div>;
  const statusLabel = factory.counts?.drifted ? "有漂移" : factory.counts?.["not-synced"] ? "未同步" : factory.counts?.["missing-source"] ? "缺少来源" : "已同步";
  const statusClass = statusLabel === "已同步" ? "factory-status-ok" : "factory-status-warn";
  return <div className="factory-page">
    <div className="factory-heading"><div><div className="factory-eyebrow"><FolderTree size={15} /> SOFTWARE FACTORY</div><h1>Software Factory</h1><p>管理基础流水线、领域 pack 和 Matt / pstack 来源版本；同步时生成实体 Skill 目录，确保 Skill Atlas 与 npx skills 都能发现。</p></div><div className="factory-actions"><button className="button button-secondary" disabled={busy} onClick={onCheck}><Check size={14} /> 检查来源</button><button className="button button-primary" disabled={busy} onClick={onRefresh}><RefreshCw size={14} /> {busy ? "同步中…" : "同步组合 profile"}</button></div></div>
    <div className="factory-summary"><div><span>组合 profile</span><strong>{factory.profile}</strong></div><div><span>状态</span><strong className={statusClass}>{statusLabel}</strong></div><div><span>已收录</span><strong>{factory.lock?.count || 0} 个 Skill</strong></div><div><span>领域 packs</span><strong>{factory.packs?.length || 0} 个</strong></div></div>
    <div className="factory-upstreams"><section className="factory-panel"><div className="factory-panel-title"><div><h2>Matt skills</h2><span>{factory.manifest.matt.repository}</span></div><span className="factory-commit">{factory.manifest.matt.commit.slice(0, 10)}</span></div><p>需求澄清、领域建模、架构、实现、测试、评审和 PR。</p></section><section className="factory-panel"><div className="factory-panel-title"><div><h2>pstack</h2><span>{factory.manifest.pstack.repository} · {factory.manifest.pstack.path}</span></div><span className="factory-commit">{factory.manifest.pstack.commit.slice(0, 10)}</span></div><p>只引入编排、并行 worker、验证 ledger 和停止规则；不依赖 Cursor runtime。</p></section></div>
    <div className="factory-section-title"><div><h2>领域 packs</h2><span>项目激活时按需选择，不会全部进入 global-runtime。</span></div><span>{factory.counts?.synced || 0}/{Object.values(factory.counts || {}).reduce((sum, value) => sum + value, 0)} 已同步</span></div>
    <div className="factory-pack-grid">{(factory.packs || []).map((pack) => <section className="factory-pack" key={pack.name}><div className="factory-pack-heading"><div><h3>{pack.name}</h3><span>{pack.synced}/{pack.total} 个 Skill 已同步</span></div><span className={pack.synced === pack.total ? "factory-dot-ok" : "factory-dot-warn"} /></div><div className="factory-pack-skills">{pack.skills.map((skill) => <span className={`factory-skill-pill factory-skill-${skill.status}`} key={skill.name} title={`${skill.source_profile}/${skill.source_path}`}>{skill.name}</span>)}</div></section>)}</div>
  </div>;
}

function OverviewPage({ skills, categories, tags, sets, usage, root, usageStatusLabel, onOpenSkills, onOpenSets }) {
  const totalSize = skills.reduce((sum, skill) => sum + Number(skill.size || 0), 0);
  const taggedSkills = skills.filter((skill) => skill.tags.length).length;
  const setSkillCount = sets.reduce((sum, set) => sum + set.skillIds.length, 0);
  const categoryStats = categories.map((name) => ({ name, count: skills.filter((skill) => skill.category === name).length })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  const tagStats = tags.map((name) => ({ name, count: skills.filter((skill) => skill.tags.includes(name)).length })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  const topUsage = [...skills].filter((skill) => skill.usageCount > 0).sort((a, b) => b.usageCount - a.usageCount || a.name.localeCompare(b.name)).slice(0, 6);
  const lastUpdated = skills.reduce((latest, skill) => Math.max(latest, Number(skill.updatedAt || 0)), 0);
  const maxCategoryCount = Math.max(1, ...categoryStats.map((item) => item.count));

  return <div className="overview-page">
    <div className="overview-heading"><div><div className="overview-eyebrow"><LayoutDashboard size={15} /> 工作台总览</div><h1>概览</h1><p>从一个页面查看本地 Skill 目录、分类、标签、集合与调用状态。</p></div><div className="overview-heading-actions"><button className="button button-secondary" onClick={onOpenSkills}><Layers3 size={14} /> 查看全部 Skills</button><button className="button button-primary" onClick={onOpenSets}><ShoppingCart size={14} /> 管理 Skill Sets</button></div></div>
    <div className="overview-stat-grid">
      <button className="overview-stat-card" onClick={onOpenSkills}><span className="overview-stat-icon overview-stat-icon-green"><Layers3 size={18} /></span><span className="overview-stat-label">全部 Skills</span><strong>{skills.length}</strong><small>已从当前目录收录</small></button>
      <div className="overview-stat-card"><span className="overview-stat-icon overview-stat-icon-blue"><FolderTree size={18} /></span><span className="overview-stat-label">分类</span><strong>{categories.length}</strong><small>{categoryStats[0]?.name || "暂无分类"} 占比最高</small></div>
      <div className="overview-stat-card"><span className="overview-stat-icon overview-stat-icon-purple"><Tag size={18} /></span><span className="overview-stat-label">标签</span><strong>{tags.length}</strong><small>{taggedSkills} 个 Skill 已打标签</small></div>
      <button className="overview-stat-card" onClick={onOpenSets}><span className="overview-stat-icon overview-stat-icon-orange"><ShoppingCart size={18} /></span><span className="overview-stat-label">Skill Sets</span><strong>{sets.length}</strong><small>共组合 {setSkillCount} 个 Skill</small></button>
      <div className="overview-stat-card"><span className="overview-stat-icon overview-stat-icon-ink"><Activity size={18} /></span><span className="overview-stat-label">调用次数</span><strong>{Number(usage.totalInvocations || 0).toLocaleString("zh-CN")}</strong><small>{usageStatusLabel}</small></div>
    </div>
    <div className="overview-grid">
      <section className="overview-panel overview-category-panel"><div className="overview-panel-heading"><div><h2>分类分布</h2><p>当前目录中的 Skill 归属情况</p></div><FolderTree size={18} /></div><div className="overview-bars">{categoryStats.slice(0, 8).map((item) => <div className="overview-bar-row" key={item.name}><div className="overview-bar-label"><span>{item.name}</span><strong>{item.count}</strong></div><div className="overview-bar-track"><span style={{ width: `${Math.max(7, (item.count / maxCategoryCount) * 100)}%` }} /></div></div>)}{!categoryStats.length ? <div className="overview-muted">还没有可展示的分类。</div> : null}</div></section>
      <section className="overview-panel"><div className="overview-panel-heading"><div><h2>最近调用</h2><p>来自 OTLP 接收端的 Skill 调用</p></div><Activity size={18} /></div>{topUsage.length ? <div className="overview-usage-list">{topUsage.map((skill, index) => <button className="overview-usage-row" key={skill.id} onClick={onOpenSkills}><span className="overview-rank">{index + 1}</span><span className="overview-usage-name"><strong>{skill.name}</strong><small>{skill.category}</small></span><strong className="overview-usage-count">{skill.usageCount.toLocaleString("zh-CN")} 次</strong></button>)}</div> : <div className="overview-empty"><Activity size={20} /><strong>暂无调用记录</strong><span>将 Codex 的 OTLP endpoint 指向 4318 后，这里会显示调用排行。</span></div>}</section>
      <section className="overview-panel"><div className="overview-panel-heading"><div><h2>标签概览</h2><p>覆盖 Skill 数最多的标签</p></div><Tag size={18} /></div>{tagStats.length ? <div className="overview-tag-list">{tagStats.slice(0, 10).map((item) => <div className="overview-tag-row" key={item.name}><span className="tag-pill">{item.name}</span><span className="overview-tag-count">{item.count} 个 Skill</span></div>)}</div> : <div className="overview-empty"><Tag size={20} /><strong>还没有标签</strong><span>在 Skill 详情或批量操作中添加标签。</span></div>}</section>
      <section className="overview-panel overview-directory-panel"><div className="overview-panel-heading"><div><h2>目录与连接</h2><p>本地文件和数据采集状态</p></div><HardDrive size={18} /></div><div className="overview-directory-list"><div><span>当前目录</span><strong title={root}>{root || "读取中…"}</strong></div><div><span>Skill 文件总大小</span><strong>{formatBytes(totalSize)}</strong></div><div><span>最近修改</span><strong>{lastUpdated ? new Date(lastUpdated).toLocaleDateString("zh-CN") : "—"}</strong></div><div><span>OTLP 接收端</span><strong className={usage.status === "connected" ? "overview-status-connected" : ""}>{usage.otlpEndpoint || "http://127.0.0.1:4318"}</strong></div></div></section>
    </div>
  </div>;
}

export function App() {
  const [skills, setSkills] = useState([]);
  const [root, setRoot] = useState("");
  const [categories, setCategories] = useState([]);
  const [usage, setUsage] = useState({ status: "not_configured", totalInvocations: 0, server: null });
  const [selectedId, setSelectedId] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [tag, setTag] = useState("all");
  const [view, setView] = useState("list");
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [sets, setSets] = useState([]);
  const [factory, setFactory] = useState(null);
  const [factoryLoading, setFactoryLoading] = useState(false);
  const [factoryBusy, setFactoryBusy] = useState(false);
  const [setDrawerOpen, setSetDrawerOpen] = useState(false);
  const [activeSection, setActiveSection] = useState("skills");
  const [setName, setSetName] = useState("");
  const [activeSetId, setActiveSetId] = useState("");
  const [batchTagOpen, setBatchTagOpen] = useState(false);
  const [batchTag, setBatchTag] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 30;
  const [detailOpen, setDetailOpen] = useState(true);
  const [activeTab, setActiveTab] = useState("Overview");
  const [draftTag, setDraftTag] = useState("");
  const [preview, setPreview] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [newSkillOpen, setNewSkillOpen] = useState(false);
  const [newSkill, setNewSkill] = useState({ name: "", category: "custom", description: "", tags: "" });
  const [creating, setCreating] = useState(false);

  const loadSkills = async (keepSelection = true) => {
    setLoading(true);
    try {
      const response = await fetch("/api/skills/");
      const data = await response.json();
      setSkills(data.skills || []); setRoot(data.root || ""); setCategories(data.categories || []); setUsage(data.usage || { status: "not_configured", totalInvocations: 0, server: null });
      setSelectedIds((previous) => new Set([...previous].filter((id) => data.skills.some((skill) => skill.id === id))));
      if (!keepSelection || !data.skills.some((skill) => skill.id === selectedId)) setSelectedId(data.skills[0]?.id || "");
    } catch { setNotice("无法读取 Skills 目录，请检查本地服务"); }
    finally { setLoading(false); }
  };

  const loadSets = async () => {
    try { const response = await fetch("/api/sets/"); const data = await response.json(); setSets(data.sets || []); }
    catch { setNotice("Set 列表读取失败"); }
  };
  const loadFactory = async () => {
    setFactoryLoading(true);
    try { const response = await fetch("/api/software-factory/"); const data = await response.json(); setFactory(data); }
    catch { setFactory({ available: false, error: "software-factory 状态读取失败" }); }
    finally { setFactoryLoading(false); }
  };
  const runFactoryAction = async (action) => {
    setFactoryBusy(true);
    try {
      const response = await fetch(`/api/software-factory/${action}/`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "software-factory 操作失败");
      setFactory(data.factory || factory); await loadSkills(false);
      showNotice(action === "refresh" ? "software-factory 组合 profile 已同步" : "来源检查完成");
    } catch (error) { showNotice(error.message || "software-factory 操作失败"); }
    finally { setFactoryBusy(false); }
  };

  useEffect(() => { loadSkills(false); loadSets(); loadFactory(); }, []);

  const selected = skills.find((skill) => skill.id === selectedId) || skills[0];
  const usageStatusLabel = usage.status === "connected" ? "已接收 OTLP" : usage.status === "idle" ? "OTLP 监听中" : usage.status === "unavailable" ? "调用统计暂不可用" : "未配置调用统计";
  useEffect(() => {
    if (!selected) { setPreview(""); return; }
    fetch(`/api/skills/${encodeURIComponent(selected.id)}/preview`).then((response) => response.json()).then((data) => setPreview(data.markdown || "")).catch(() => setPreview(""));
  }, [selected?.id]);

  const tags = useMemo(() => [...new Set(skills.flatMap((skill) => skill.tags))].sort(), [skills]);
  const filtered = useMemo(() => skills.filter((skill) => {
    const text = `${skill.name} ${skill.description} ${skill.id} ${skill.tags.join(" ")}`.toLowerCase();
    return text.includes(query.toLowerCase()) && (category === "all" || skill.category === category) && (tag === "all" || skill.tags.includes(tag));
  }), [skills, query, category, tag]);
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const paged = filtered.slice((page - 1) * pageSize, page * pageSize);
  const pageNumbers = totalPages <= 7 ? Array.from({ length: totalPages }, (_, index) => index + 1) : Array.from({ length: 7 }, (_, index) => Math.min(Math.max(page - 3, 1), totalPages - 6) + index);
  useEffect(() => { setPage(1); }, [query, category, tag]);
  useEffect(() => { if (page > totalPages) setPage(totalPages); }, [page, totalPages]);

  const showNotice = (message) => { setNotice(message); window.setTimeout(() => setNotice(""), 2300); };
  const selectedSkills = useMemo(() => skills.filter((skill) => selectedIds.has(skill.id)), [skills, selectedIds]);
  const selectedCount = selectedIds.size;
  const allPageSelected = paged.length > 0 && paged.every((skill) => selectedIds.has(skill.id));
  const toggleSelected = (id) => setSelectedIds((previous) => { const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const togglePage = () => setSelectedIds((previous) => { const next = new Set(previous); paged.forEach((skill) => { if (allPageSelected) next.delete(skill.id); else next.add(skill.id); }); return next; });
  const createSet = async () => {
    if (!setName.trim() || !selectedCount) return;
    const response = await fetch("/api/sets/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: setName.trim(), skillIds: [...selectedIds] }) });
    const data = await response.json();
    if (!response.ok) { showNotice(data.error || "Set 保存失败"); return; }
    setSets((previous) => [...previous, data.set]); setSetName(""); setSelectedIds(new Set()); setSetDrawerOpen(false); showNotice(`Set「${data.set.name}」已保存`);
  };
  const addToSet = async (set) => {
    const skillIds = [...new Set([...set.skillIds, ...selectedIds])];
    const response = await fetch(`/api/sets/${encodeURIComponent(set.id)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ skillIds }) });
    const data = await response.json();
    if (!response.ok) { showNotice(data.error || "Set 更新失败"); return; }
    setSets((previous) => previous.map((item) => item.id === set.id ? data.set : item)); setSelectedIds(new Set()); setSetDrawerOpen(false); showNotice(`已加入 Set「${set.name}」`);
  };
  const deleteSet = async (set) => {
    const response = await fetch(`/api/sets/${encodeURIComponent(set.id)}`, { method: "DELETE" });
    if (!response.ok) { showNotice("Set 删除失败"); return; }
    setSets((previous) => previous.filter((item) => item.id !== set.id)); if (activeSetId === set.id) setActiveSetId(""); showNotice(`Set「${set.name}」已删除`);
  };
  const batchUpdateTags = async () => {
    const value = batchTag.trim(); if (!value || !selectedCount) return;
    const results = await Promise.all([...selectedIds].map(async (id) => fetch(`/api/skills/${encodeURIComponent(id)}/tags`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tags: [...new Set([...(skills.find((skill) => skill.id === id)?.tags || []), value])] }) })));
    if (results.some((response) => !response.ok)) { showNotice("部分标签保存失败"); return; }
    await loadSkills(); setBatchTag(""); setBatchTagOpen(false); showNotice(`已为 ${selectedCount} 个 Skill 添加标签`);
  };
  const openSkillFolder = async (skill) => {
    if (!skill) return;
    try {
      const response = await fetch(`/api/skills/${encodeURIComponent(skill.id)}/open`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "文件夹打开失败");
      showNotice("已在 Finder 中打开 Skill 文件夹");
    } catch (error) { showNotice(error.message || "文件夹打开失败，请检查本地服务"); }
  };
  const updateTags = async (nextTags) => {
    if (!selected) return;
    const response = await fetch(`/api/skills/${encodeURIComponent(selected.id)}/tags`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tags: nextTags }) });
    if (!response.ok) { showNotice("标签保存失败"); return; }
    await loadSkills(); showNotice("标签已写入 .skill-manager/tags.json");
  };
  const addTag = () => { const next = draftTag.trim(); if (!next || !selected || selected.tags.includes(next)) return; setDraftTag(""); updateTags([...selected.tags, next]); };
  const removeTag = (value) => updateTags(selected.tags.filter((item) => item !== value));
  const createSkill = async (event) => {
    event.preventDefault();
    setCreating(true);
    try {
      const response = await fetch("/api/skills/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...newSkill, tags: newSkill.tags.split(",").map((item) => item.trim()).filter(Boolean) }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "创建失败");
      setNewSkillOpen(false); setNewSkill({ name: "", category: "custom", description: "", tags: "" });
      await loadSkills(false); setSelectedId(data.id); showNotice("Skill 目录和 SKILL.md 已创建");
    } catch (error) { showNotice(error.message); }
    finally { setCreating(false); }
  };
  const useSet = (set) => { setSelectedIds(new Set(set.skillIds)); setActiveSection("skills"); setSetDrawerOpen(false); showNotice(`已选择 Set「${set.name}」的 ${set.skillIds.length} 个 Skill`); };

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Layers3 size={20} /></div><div><strong>Skill Atlas</strong><span>Classify. Tag. Maintain.</span></div></div>
      <nav className="sidebar-nav">
        <div className="nav-group"><div className="nav-group-label">管理</div><button className={`nav-item ${activeSection === "overview" ? "nav-item-active" : ""}`} onClick={() => setActiveSection("overview")}><LayoutDashboard size={17} /><span>概览</span></button><button className={`nav-item ${activeSection === "skills" ? "nav-item-active" : ""}`} onClick={() => setActiveSection("skills")}><Layers3 size={17} /><span>全部 Skills</span><em>{skills.length}</em></button><button className={`nav-item ${activeSection === "sets" ? "nav-item-active" : ""}`} onClick={() => setActiveSection("sets")}><ShoppingCart size={16} /><span>Skill Sets</span><em>{sets.length}</em></button><button className={`nav-item ${activeSection === "factory" ? "nav-item-active" : ""}`} onClick={() => setActiveSection("factory")}><FolderTree size={17} /><span>Software Factory</span><em>{factory?.packs?.length || 0}</em></button><button className="nav-item"><FolderTree size={17} /><span>目录浏览</span></button></div>
        <div className="nav-group"><div className="nav-group-label">分类</div><button className={`nav-item ${category === "all" ? "nav-item-active-soft" : ""}`} onClick={() => setCategory("all")}><FolderOpen size={16} /><span>全部分类</span><em>{skills.length}</em></button>{categories.slice(0, 8).map((item) => <button className={`nav-item ${category === item ? "nav-item-active-soft" : ""}`} key={item} onClick={() => setCategory(item)}><FolderOpen size={16} /><span>{item}</span><em>{skills.filter((skill) => skill.category === item).length}</em></button>)}</div>
        <div className="nav-group"><div className="nav-group-label">标签</div>{tags.slice(0, 7).map((item) => <button className={`nav-item ${tag === item ? "nav-item-active-soft" : ""}`} key={item} onClick={() => setTag(item)}><Tag size={15} /><span>{item}</span><em>{skills.filter((skill) => skill.tags.includes(item)).length}</em></button>)}</div>
      </nav>
      <div className="sidebar-spacer" />
      <div className="root-summary"><HardDrive size={15} /><div><strong>当前目录</strong><span title={root}>{root || "读取中…"}</span></div><button aria-label="刷新目录" onClick={() => loadSkills(false)}><RefreshCw size={14} /></button></div>
      <button className="settings-link"><Settings2 size={16} /> 目录设置</button>
    </aside>
    <main className="main-panel">
      <header className="topbar"><div><div className="breadcrumbs"><span>{activeSection === "overview" ? "概览" : activeSection === "sets" ? "Skill Sets" : activeSection === "factory" ? "Software Factory" : "全部 Skills"}</span>{activeSection !== "overview" ? <span className="crumb-count">{activeSection === "sets" ? sets.length : activeSection === "factory" ? (factory?.packs?.length || 0) : skills.length}</span> : null}</div><p className="root-path">{activeSection === "overview" ? "Skill Atlas 工作台" : activeSection === "sets" ? "按用途组合的 Skill 集合" : root}</p></div><div className="topbar-actions"><span className="synced-pill"><span className="status-dot status-dot-green" /> 已连接本地目录</span><span className={`synced-pill usage-pill usage-${usage.status}`} title={usage.otlpEndpoint || usage.server || "请将 Codex OTLP endpoint 指向本机 4318 端口"}><Activity size={13} /> {usageStatusLabel}</span><button className="button button-primary" onClick={() => setNewSkillOpen(true)}> <Plus size={16} /> 新建 Skill</button></div></header>
      <div className={`library-layout ${detailOpen ? "" : "detail-closed"}`}>
        <section className="library-content">
          {activeSection === "overview" ? <OverviewPage skills={skills} categories={categories} tags={tags} sets={sets} usage={usage} root={root} usageStatusLabel={usageStatusLabel} onOpenSkills={() => setActiveSection("skills")} onOpenSets={() => setActiveSection("sets")} /> : activeSection === "factory" ? <FactoryPage factory={factory} loading={factoryLoading} busy={factoryBusy} onCheck={() => runFactoryAction("check")} onRefresh={() => runFactoryAction("refresh")} /> : activeSection === "sets" ? <SetsPage sets={sets} skills={skills} onUse={useSet} onDelete={deleteSet} onBack={() => setActiveSection("skills")} /> : <>
          <div className="toolbar"><label className="search-box"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索 Skill 名称、路径、描述或标签…" /><kbd>⌘ K</kbd></label><div className="toolbar-actions"><button className="button button-ghost" onClick={() => loadSkills()}><RefreshCw size={14} /> 刷新</button><div className="view-switcher"><button className={view === "grid" ? "view-active" : ""} onClick={() => setView("grid")}><Grid2X2 size={16} /></button><button className={view === "list" ? "view-active" : ""} onClick={() => setView("list")}><List size={17} /></button></div></div></div>
          <div className="filters"><button className={`filter-select ${category === "all" ? "" : "filter-selected"}`} onClick={() => setCategory("all")}>分类：{category === "all" ? "全部" : category} <ChevronDown size={13} /></button>{tags.map((item) => <button key={item} className={`filter-chip ${tag === item ? "filter-selected" : ""}`} onClick={() => setTag(tag === item ? "all" : item)}>{item}</button>)}<button className="filter-add" onClick={() => selected && setDraftTag("新标签")}><Plus size={15} /></button></div>
          <div className="skills-heading"><span>{loading ? "正在扫描目录…" : `${filtered.length} 个 Skill${filtered.length ? ` · 第 ${page}/${totalPages} 页` : ""}`}</span><span className="result-hint">{usage.status === "connected" ? `OTLP 已记录 ${usage.totalInvocations.toLocaleString("zh-CN")} 次 Skill 调用` : usage.status === "idle" ? "OTLP 接收端口：4318" : "标签写入 `.skill-manager/tags.json`"}</span></div>
          {selectedCount ? <div className="batch-toolbar"><div className="batch-summary"><button className="selection-check-button" onClick={togglePage} aria-label="切换当前页选择"><CheckSquare size={16} /></button><strong>已选择 {selectedCount} 项</strong><span>可跨分页保留</span></div><div className="batch-actions"><button className="button button-secondary" onClick={() => setSetDrawerOpen(true)}><ShoppingCart size={14} /> 加入 Set</button><button className="button button-secondary" onClick={() => setBatchTagOpen(true)}><Tag size={14} /> 批量打标签</button><button className="icon-button" onClick={() => setSelectedIds(new Set())} aria-label="清空选择"><X size={15} /></button></div></div> : null}
          {filtered.length ? <><button className={`page-select ${allPageSelected ? "page-select-active" : ""}`} onClick={togglePage}><CheckSquare size={14} /> {allPageSelected ? "取消全选当前页" : "全选当前页"}</button>{view === "list" ? <div className="skill-list-view"><div className="skill-list-header"><span></span><span>Skill</span><span>分类 / 路径</span><span>标签</span><span>调用</span><span>状态</span><span></span></div>{paged.map((skill, index) => <article className={`skill-row ${selectedIds.has(skill.id) ? "skill-row-selected" : ""} ${selected?.id === skill.id && detailOpen ? "skill-row-focused" : ""}`} key={skill.id} onClick={() => { setSelectedId(skill.id); setDetailOpen(true); setActiveTab("Overview"); }}><input className="selection-check" type="checkbox" checked={selectedIds.has(skill.id)} onChange={() => toggleSelected(skill.id)} onClick={(event) => event.stopPropagation()} aria-label={`选择 ${skill.name}`} /><div className="skill-row-main"><IconBadge index={(page - 1) * pageSize + index} size={18} /><div className="skill-row-info"><div className="skill-name-row"><h2>{skill.name}</h2><span className="status-dot status-dot-green" /></div><p>{skill.description || "暂无描述，可在 SKILL.md frontmatter 中补充。"}</p></div></div><div className="skill-row-path"><strong>{skill.category}</strong><span title={skill.id}>{skill.id}</span></div><div className="skill-row-tags">{skill.tags.length ? skill.tags.slice(0, 3).map((item) => <span className="tag-pill" key={item}>{item}</span>) : <span className="tag-pill tag-empty">未标记</span>}{skill.tags.length > 3 ? <span className="tag-more">+{skill.tags.length - 3}</span> : null}</div><span className="skill-row-usage"><Activity size={12} /> {skill.usageCount ? `${skill.usageCount} 次` : "暂无调用"}</span><span className="managed-label">已收录</span><button className="more-button folder-open-button" title="在 Finder 中打开文件夹" aria-label={`打开 ${skill.name} 文件夹`} onClick={(event) => { event.stopPropagation(); openSkillFolder(skill); }}><FolderOpen size={16} /></button></article>)}</div> : <div className="skill-grid">{paged.map((skill, index) => <article className={`skill-card ${selectedIds.has(skill.id) ? "skill-card-selected" : ""} ${selected?.id === skill.id && detailOpen ? "skill-card-focused" : ""}`} key={skill.id} onClick={() => { setSelectedId(skill.id); setDetailOpen(true); setActiveTab("Overview"); }}><div className="skill-card-top"><div className="skill-title"><input className="selection-check" type="checkbox" checked={selectedIds.has(skill.id)} onChange={() => toggleSelected(skill.id)} onClick={(event) => event.stopPropagation()} aria-label={`选择 ${skill.name}`} /><IconBadge index={(page - 1) * pageSize + index} /><div><div className="skill-name-row"><h2>{skill.name}</h2><span className="status-dot status-dot-green" /></div><p>{skill.description || "暂无描述，可在 SKILL.md frontmatter 中补充。"}</p></div></div><span className="managed-label">已收录</span></div><div className="skill-tags">{skill.tags.length ? skill.tags.map((item) => <span className="tag-pill" key={item}>{item}</span>) : <span className="tag-pill tag-empty">未标记</span>}</div><div className="skill-card-meta"><span><FolderOpen size={13} /> {skill.category}</span><span>·</span><span>{formatBytes(skill.size)}</span><span>·</span><span>{skill.id}</span><span className="usage-count"><Activity size={12} /> {skill.usageCount ? `${skill.usageCount} 次` : "暂无调用"}</span><button className="more-button folder-open-button" title="在 Finder 中打开文件夹" aria-label={`打开 ${skill.name} 文件夹`} onClick={(event) => { event.stopPropagation(); openSkillFolder(skill); }}><FolderOpen size={16} /></button></div></article>)}</div>}<div className="pagination"><button className="pagination-button" disabled={page === 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>上一页</button><div className="pagination-pages">{pageNumbers.map((pageNumber) => <button key={pageNumber} className={page === pageNumber ? "pagination-current" : "pagination-button"} onClick={() => setPage(pageNumber)}>{pageNumber}</button>)}</div><button className="pagination-button" disabled={page === totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>下一页</button></div></> : <div className="empty-state"><FolderTree size={22} /><strong>没有匹配的 Skill</strong><span>换一个搜索词或清除筛选条件。</span></div>}
          </>}
        </section>
        {activeSection === "skills" && detailOpen && selected ? <aside className="detail-panel"><div className="detail-header"><div className="detail-heading"><IconBadge index={skills.indexOf(selected)} size={24} /><div><h2>{selected.name}</h2><div className="detail-subline"><span className="status-dot status-dot-green" /> 已发现 <span>·</span><span>{selected.category}</span><span>·</span><span>{formatBytes(selected.size)}</span></div></div></div><button className="icon-button" aria-label="关闭详情" onClick={() => setDetailOpen(false)}><X size={17} /></button></div><p className="detail-description">{selected.description || "暂无描述。"}</p><div className="detail-tags">{selected.tags.map((item) => <span className="tag-pill" key={item}>{item}<button aria-label={`移除标签 ${item}`} onClick={() => removeTag(item)}>×</button></span>)}{!selected.tags.length ? <span className="tag-pill tag-empty">暂无标签</span> : null}</div><div className="tag-editor"><input value={draftTag} onChange={(event) => setDraftTag(event.target.value)} onKeyDown={(event) => event.key === "Enter" && addTag()} placeholder="添加标签…" /><button className="button button-secondary" onClick={addTag}><Plus size={14} /> 添加</button></div><div className="source-line"><FolderOpen size={15} /><span title={selected.path}>{selected.id}/SKILL.md</span><span>·</span><span>{selected.frontmatter ? "有 frontmatter" : "无 frontmatter"}</span></div><button className="button button-secondary detail-folder-button" onClick={() => openSkillFolder(selected)}><FolderOpen size={14} /> 打开文件夹</button><div className="detail-tabs">{["Overview", "SKILL.md"].map((tabName) => <button key={tabName} className={activeTab === tabName ? "detail-tab-active" : ""} onClick={() => setActiveTab(tabName)}>{tabName}</button>)}</div>{activeTab === "Overview" ? <div className="overview-content"><div className="readme-heading"><BookOpen size={18} /><h3>目录信息</h3></div><div className="readme"><h3>分类：{selected.category}</h3><p>{selected.id}</p><h4>文件状态</h4><ul><li>文件大小：{formatBytes(selected.size)}</li><li>标签数量：{selected.tags.length}</li><li>最后修改：{new Date(selected.updatedAt).toLocaleString("zh-CN")}</li></ul></div></div> : <div className="readme markdown-preview"><div className="readme-heading"><h3>SKILL.md 预览</h3><button className="button button-ghost" onClick={() => navigator.clipboard?.writeText(preview)}><Copy size={13} /> 复制</button></div><pre>{preview || "读取中…"}</pre></div>}<div className="deployment-section"><div className="section-heading"><div><h3><Tag size={18} /> 标签管理</h3><span>修改后立即保存到真实目录元数据</span></div><span className="deployed-badge"><Check size={13} /> 已连接</span></div></div></aside> : null}
      </div>
    </main>
    {newSkillOpen ? <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setNewSkillOpen(false)}><form className="modal-card" onSubmit={createSkill}><div className="modal-heading"><div><h2>新建 Skill</h2><p>会在当前 Skills 目录中创建分类文件夹、SKILL.md 和标签记录。</p></div><button type="button" className="icon-button" aria-label="关闭新建窗口" onClick={() => setNewSkillOpen(false)}><X size={17} /></button></div><label>名称<input required pattern="[A-Za-z0-9_\\-一-龥]+" value={newSkill.name} onChange={(event) => setNewSkill({ ...newSkill, name: event.target.value })} placeholder="例如：release-notes" /></label><label>分类<input required pattern="[A-Za-z0-9_\\-一-龥]+" value={newSkill.category} onChange={(event) => setNewSkill({ ...newSkill, category: event.target.value })} placeholder="例如：custom" /></label><label>描述<textarea value={newSkill.description} onChange={(event) => setNewSkill({ ...newSkill, description: event.target.value })} placeholder="一句话说明这个 Skill 的用途" /></label><label>标签<span className="field-hint">用逗号分隔，可留空</span><input value={newSkill.tags} onChange={(event) => setNewSkill({ ...newSkill, tags: event.target.value })} placeholder="例如：文档, 自动化" /></label><div className="modal-actions"><button type="button" className="button button-ghost" onClick={() => setNewSkillOpen(false)}>取消</button><button disabled={creating} className="button button-primary" type="submit">{creating ? "创建中…" : "创建并写入目录"}</button></div></form></div> : null}
    {setDrawerOpen ? <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setSetDrawerOpen(false)}><section className="set-drawer"><div className="modal-heading"><div><h2><ShoppingCart size={19} /> Skill Set</h2><p>把已选择的 {selectedCount} 个 Skill 保存成一组，后续可批量复用。</p></div><button className="icon-button" aria-label="关闭 Set" onClick={() => setSetDrawerOpen(false)}><X size={17} /></button></div><label>新建 Set<input value={setName} onChange={(event) => setSetName(event.target.value)} onKeyDown={(event) => event.key === "Enter" && createSet()} placeholder="例如：内容生产工具箱" /></label><button className="button button-primary set-save-button" disabled={!setName.trim() || !selectedCount} onClick={createSet}><Save size={14} /> 保存为新 Set</button><div className="set-section-title"><span>已有 Set</span><span>{sets.length} 组</span></div>{sets.length ? <div className="set-list">{sets.map((set) => <div className={`set-item ${activeSetId === set.id ? "set-item-active" : ""}`} key={set.id} onClick={() => setActiveSetId(set.id)}><div><strong>{set.name}</strong><span>{set.skillIds.length} 个 Skill</span></div><div className="set-item-actions"><button className="button button-secondary" onClick={() => addToSet(set)}><BookmarkPlus size={13} /> 加入</button><button className="icon-button" aria-label={`删除 ${set.name}`} onClick={() => deleteSet(set)}><Trash2 size={14} /></button></div></div>)}</div> : <div className="set-empty"><ShoppingCart size={18} /><span>还没有 Set，先保存一组吧。</span></div>}</section></div> : null}
    {batchTagOpen ? <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setBatchTagOpen(false)}><form className="modal-card" onSubmit={(event) => { event.preventDefault(); batchUpdateTags(); }}><div className="modal-heading"><div><h2>批量打标签</h2><p>为已选择的 {selectedCount} 个 Skill 追加一个标签。</p></div><button type="button" className="icon-button" aria-label="关闭批量标签" onClick={() => setBatchTagOpen(false)}><X size={17} /></button></div><label>标签<input autoFocus required value={batchTag} onChange={(event) => setBatchTag(event.target.value)} placeholder="例如：重点维护" /></label><div className="modal-actions"><button type="button" className="button button-ghost" onClick={() => setBatchTagOpen(false)}>取消</button><button className="button button-primary" type="submit"><Tag size={14} /> 写入标签</button></div></form></div> : null}
    {notice ? <div className="toast"><Check size={15} /> {notice}</div> : null}
  </div>;
}
