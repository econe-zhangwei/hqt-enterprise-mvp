import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  LayoutDashboard, 
  Building2, 
  FileSearch, 
  BotMessageSquare, 
  TicketCheck, 
  LogOut,
  ChevronRight,
  Sparkles,
  Menu,
  X
} from 'lucide-react';
import { api, type MatchData, type MatchResult, type MatchSummary } from '../services/api';

// Views
import Overview from './views/Overview';
import Profile from './views/Profile';
import Match from './views/Match';
import Assistant from './views/Assistant';
import Ticket from './views/Ticket';

const VIEWS = [
  { id: 'overview', label: '总览', icon: LayoutDashboard, desc: '查看当前企业政策匹配整体状态与建议动作' },
  { id: 'profile', label: '企业信息', icon: Building2, desc: '维护企业画像字段，作为政策匹配输入' },
  { id: 'match', label: '政策匹配', icon: FileSearch, desc: '重点查看可申报与需完善政策' },
  { id: 'assistant', label: 'AI 助手', icon: BotMessageSquare, desc: '围绕当前企业画像和政策结果进行问答解释' },
  { id: 'ticket', label: '工单中心', icon: TicketCheck, desc: '提交人工顾问协助并跟踪处理状态' },
];

const EMPTY_SUMMARY: MatchSummary = { eligible_count: 0, potential_count: 0 };

export default function Workspace({ user: initialUser, onLogout }: { user: string | null; onLogout: () => void }) {
  const [activeView, setActiveView] = useState('overview');
  const [user, setUser] = useState(initialUser || 'enterprise');
  const [enterpriseId, setEnterpriseId] = useState<string | null>(localStorage.getItem('hqt_enterprise_id'));
  const [matchResults, setMatchResults] = useState<MatchResult[]>([]);
  const [summary, setSummary] = useState<MatchSummary>(EMPTY_SUMMARY);
  const [topPolicyId, setTopPolicyId] = useState<string | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const activeViewData = VIEWS.find(v => v.id === activeView);

  useEffect(() => {
    let cancelled = false;
    api.getMe()
      .then((data) => {
        if (!cancelled) {
          setUser(data.subject);
        }
      })
      .catch(() => {
        if (!cancelled) {
          onLogout();
        }
      });
    return () => {
      cancelled = true;
    };
  }, [onLogout]);

  useEffect(() => {
    if (enterpriseId) {
      localStorage.setItem('hqt_enterprise_id', enterpriseId);
    } else {
      localStorage.removeItem('hqt_enterprise_id');
    }
  }, [enterpriseId]);

  const handleResults = (res: MatchData) => {
    setMatchResults(res.results);
    setSummary(res.summary);
    setTopPolicyId(res.results.length > 0 ? res.results[0].policy_id : null);
  };

  const handleMatchRequested = () => {
    setMatchResults([]);
    setSummary(EMPTY_SUMMARY);
    setTopPolicyId(null);
    setActiveView('match');
  };

  const handleNavigate = (viewId: string) => {
    setActiveView(viewId);
    setIsMobileMenuOpen(false);
  };

  const renderNavButton = (view: (typeof VIEWS)[number], compact = false) => {
    const Icon = view.icon;
    const isActive = activeView === view.id;

    return (
      <button
        key={view.id}
        onClick={() => handleNavigate(view.id)}
        className={
          compact
            ? `flex min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-2xl px-2 py-2.5 text-[11px] font-medium transition-colors ${
                isActive ? 'bg-[#E8EEF5] text-[#1E3A5F]' : 'text-slate-500'
              }`
            : `w-full flex items-center gap-3 px-3 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-white text-[#1E3A5F] shadow-sm ring-1 ring-white/30'
                  : 'hover:bg-white/8 hover:text-white'
              }`
        }
      >
        <Icon className={`shrink-0 ${compact ? 'w-4 h-4' : `w-4 h-4 ${isActive ? 'text-[#1E3A5F]' : 'text-slate-300'}`}`} />
        <span className={compact ? 'truncate' : ''}>{view.label}</span>
        {!compact && isActive && <ChevronRight className="w-4 h-4 ml-auto opacity-50" />}
      </button>
    );
  };

  return (
    <div className="min-h-screen bg-slate-100 lg:flex lg:h-screen lg:overflow-hidden">
      {isMobileMenuOpen && (
        <div className="fixed inset-0 z-40 bg-slate-950/35 lg:hidden" onClick={() => setIsMobileMenuOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`fixed inset-y-0 left-0 z-50 w-[280px] bg-[#1E3A5F] text-slate-200 flex flex-col border-r border-[#17304f] shrink-0 transition-transform duration-200 lg:static lg:w-64 ${
        isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      }`}>
        <div className="h-16 flex items-center px-6 border-b border-white/10">
          <div className="flex items-center gap-2 text-white">
            <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center border border-white/15">
              <Building2 className="w-4 h-4" />
            </div>
            <span className="font-semibold tracking-tight">惠企通</span>
          </div>
          <button
            type="button"
            aria-label="关闭菜单"
            onClick={() => setIsMobileMenuOpen(false)}
            className="ml-auto inline-flex h-10 w-10 items-center justify-center rounded-xl text-slate-200 hover:bg-white/10 lg:hidden"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 py-6 px-4 space-y-1 overflow-y-auto">
          {VIEWS.map((view) => renderNavButton(view))}
        </nav>

        <div className="p-4 border-t border-white/10">
          <div className="bg-white/8 rounded-xl p-4 border border-white/10">
            <div className="text-xs text-slate-300/80 mb-1">当前登录</div>
            <div className="text-sm text-white font-medium truncate mb-4">{user}</div>
            <button 
              onClick={onLogout}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-[#C73E3A]/12 text-[#FFD6D6] hover:bg-[#C73E3A]/18 transition-colors text-sm font-medium"
            >
              <LogOut className="w-4 h-4" />
              退出登录
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex min-h-screen w-full flex-col relative lg:ml-0 lg:h-full lg:min-h-0 lg:flex-1 lg:overflow-hidden">
        {/* Header */}
        <header className="sticky top-0 bg-white/95 backdrop-blur-sm border-b border-slate-200 px-4 py-3 sm:px-6 lg:h-20 lg:px-8 lg:py-0 flex items-center justify-between shrink-0 z-30">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              aria-label="打开菜单"
              onClick={() => setIsMobileMenuOpen(true)}
              className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-slate-700 lg:hidden"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="min-w-0">
              <h1 className="text-lg sm:text-xl font-semibold text-slate-900 tracking-tight truncate">{activeViewData?.label}</h1>
              <p className="text-xs sm:text-sm text-slate-500 mt-0.5 line-clamp-2">{activeViewData?.desc}</p>
            </div>
          </div>
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-50 border border-slate-200 text-xs font-medium text-slate-600">
            <Sparkles className="w-3.5 h-3.5 text-[#2F6BFF]" />
            企业画像 → 智能匹配 → AI 解读 → 人工协同
          </div>
        </header>

        {/* View Container */}
        <div className="flex-1 overflow-y-auto px-4 py-4 pb-24 sm:px-6 lg:px-8 lg:py-8 lg:pb-8">
          <div className="max-w-6xl mx-auto min-h-full">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeView}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="min-h-full"
              >
                {activeView === 'overview' && (
                  <Overview 
                    summary={summary} 
                    matchResults={matchResults} 
                    onNavigate={handleNavigate} 
                  />
                )}
                {activeView === 'profile' && (
                  <Profile 
                    enterpriseId={enterpriseId}
                    onSave={(id) => setEnterpriseId(id)} 
                    onMatch={handleMatchRequested} 
                  />
                )}
                {activeView === 'match' && (
                  <Match 
                    enterpriseId={enterpriseId}
                    results={matchResults}
                    summary={summary}
                    onResults={handleResults}
                    onPolicySelect={(policyId) => setTopPolicyId(policyId)}
                  />
                )}
                {activeView === 'assistant' && (
                  <Assistant 
                    enterpriseId={enterpriseId}
                    topPolicyId={topPolicyId}
                    onHandoff={() => setActiveView('ticket')}
                  />
                )}
                {activeView === 'ticket' && (
                  <Ticket 
                    enterpriseId={enterpriseId}
                  />
                )}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </main>

      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white/95 px-2 py-2 backdrop-blur-sm lg:hidden">
        <div className="mx-auto flex max-w-md items-stretch gap-1">
          {VIEWS.map((view) => renderNavButton(view, true))}
        </div>
      </nav>
    </div>
  );
}
