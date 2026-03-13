import { motion } from 'motion/react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Building2, FileSearch, BotMessageSquare, TicketCheck, ArrowRight, Sparkles } from 'lucide-react';

export default function Overview({ summary, matchResults, onNavigate }: any) {
  const total = (summary.eligible_count || 0) + (summary.potential_count || 0);

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* Hero Section */}
      <div className="rounded-3xl p-5 sm:p-8 md:p-12 text-white relative overflow-hidden border border-[#214A73] bg-[linear-gradient(135deg,#1E3A5F_0%,#274d78_55%,#335f8f_100%)] shadow-[0_18px_40px_rgba(30,58,95,0.18)]">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_100%_0%,rgba(255,255,255,0.16)_0%,transparent_34%)]" />
        <div className="absolute inset-y-0 right-0 w-1/2 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),transparent)]" />
        
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/12 border border-white/20 text-xs font-medium mb-4 sm:mb-6">
            <span className="w-2 h-2 rounded-full bg-[#7DD3FC]" />
            政策服务驾驶舱
          </div>
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-semibold mb-4 leading-tight">围绕企业画像、政策匹配与人工协同<br />构建统一的政策办理工作台</h2>
          <p className="text-slate-200/85 text-base sm:text-lg mb-6 sm:mb-8 leading-relaxed">
            面向政务服务和企业辅导场景，统一查看匹配结果、重点政策、材料准备与协同处理进度。
          </p>
          
          <div className="flex flex-wrap gap-3">
            <span className="px-3 py-2 rounded-xl bg-white/10 border border-white/15 text-xs sm:text-sm font-medium">匹配结果可解释</span>
            <span className="px-3 py-2 rounded-xl bg-white/10 border border-white/15 text-xs sm:text-sm font-medium">申报优先级可排序</span>
            <span className="px-3 py-2 rounded-xl bg-white/10 border border-white/15 text-xs sm:text-sm font-medium">复杂问题转人工复核</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8">
        {/* Stats */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-zinc-900">当前业务状态</h3>
              <p className="text-sm text-slate-500">先看结果规模，再安排当前办理动作。</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <Card className="border-[#CFE7DC] bg-[linear-gradient(180deg,#F6FCF8_0%,#FFFFFF_100%)]">
              <CardContent className="p-6">
                <div className="w-10 h-10 rounded-xl bg-[#E5F3EC] text-[#2E8B57] flex items-center justify-center mb-4">
                  <FileSearch className="w-5 h-5" />
                </div>
                <div className="text-3xl font-semibold text-slate-900 mb-1">{summary.eligible_count || 0}</div>
                <div className="text-sm font-medium text-slate-700">可申报</div>
                <div className="text-xs text-slate-500 mt-1">满足条件，可进入材料准备</div>
              </CardContent>
            </Card>
            
            <Card className="border-[#F0DFC0] bg-[linear-gradient(180deg,#FFFBF3_0%,#FFFFFF_100%)]">
              <CardContent className="p-6">
                <div className="w-10 h-10 rounded-xl bg-[#F7E8C9] text-[#B7791F] flex items-center justify-center mb-4">
                  <FileSearch className="w-5 h-5" />
                </div>
                <div className="text-3xl font-semibold text-slate-900 mb-1">{summary.potential_count || 0}</div>
                <div className="text-sm font-medium text-slate-700">需完善</div>
                <div className="text-xs text-slate-500 mt-1">补齐条件后再进入申报流程</div>
              </CardContent>
            </Card>
            
            <Card className="border-[#D6E3F0] bg-[linear-gradient(180deg,#F6FAFE_0%,#FFFFFF_100%)]">
              <CardContent className="p-6">
                <div className="w-10 h-10 rounded-xl bg-[#E3ECF7] text-[#1E3A5F] flex items-center justify-center mb-4">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div className="text-3xl font-semibold text-slate-900 mb-1">{total}</div>
                <div className="text-sm font-medium text-slate-700">重点关注</div>
                <div className="text-xs text-slate-500 mt-1">当前建议纳入重点办理的政策</div>
              </CardContent>
            </Card>
            
            <Card className="border-[#DEE5EE] bg-[linear-gradient(180deg,#F8FAFC_0%,#FFFFFF_100%)]">
              <CardContent className="p-6">
                <div className="w-10 h-10 rounded-xl bg-[#E8EEF5] text-[#48627C] flex items-center justify-center mb-4">
                  <TicketCheck className="w-5 h-5" />
                </div>
                <div className="text-3xl font-semibold text-slate-900 mb-1">-</div>
                <div className="text-sm font-medium text-slate-700">协同进度</div>
                <div className="text-xs text-slate-500 mt-1">人工复核与顾问协同状态</div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>建议优先处理</CardTitle>
              <CardDescription>让动作比说明更靠前。</CardDescription>
            </CardHeader>
            <CardContent>
              {matchResults && matchResults.length > 0 ? (
                <ul className="space-y-3">
                  {matchResults.slice(0, 3).map((r: any, i: number) => (
                    <li key={i} className="flex items-start gap-3 text-sm">
                      <div className="w-1.5 h-1.5 rounded-full bg-zinc-400 mt-2 shrink-0" />
                      <span className="text-slate-700">
                        <strong className="text-slate-900 font-medium">{r.policy_title}</strong>：
                        {r.next_action === 'prepare_materials' ? '准备申报材料' : '补齐条件后再评估'}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="text-sm text-slate-500 bg-slate-50 p-4 rounded-xl border border-slate-100">
                  请先在“企业信息”页提交画像并执行政策匹配。
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Quick Links */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-zinc-900">快捷入口</h3>
              <p className="text-sm text-slate-500">以办理动作组织常用入口。</p>
            </div>
          </div>

          <div className="grid gap-3">
            <button onClick={() => onNavigate('profile')} className="flex items-center gap-3 sm:gap-4 p-4 rounded-2xl bg-white border border-slate-200 hover:border-[#1E3A5F]/35 hover:shadow-sm transition-all text-left group">
              <div className="w-11 h-11 sm:w-12 sm:h-12 rounded-xl bg-[#1E3A5F] text-white flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                <Building2 className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <div className="font-semibold text-slate-900 mb-0.5">完善企业画像</div>
                <div className="text-xs text-slate-500">维护企业基础信息、经营情况与资质能力</div>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-[#1E3A5F] transition-colors" />
            </button>
            
            <button onClick={() => onNavigate('match')} className="flex items-center gap-3 sm:gap-4 p-4 rounded-2xl bg-white border border-slate-200 hover:border-[#1E3A5F]/35 hover:shadow-sm transition-all text-left group">
              <div className="w-11 h-11 sm:w-12 sm:h-12 rounded-xl bg-[#1E3A5F] text-white flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                <FileSearch className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <div className="font-semibold text-slate-900 mb-0.5">查看匹配结果</div>
                <div className="text-xs text-slate-500">识别可申报政策与待补齐条件</div>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-[#1E3A5F] transition-colors" />
            </button>
            
            <button onClick={() => onNavigate('assistant')} className="flex items-center gap-3 sm:gap-4 p-4 rounded-2xl bg-white border border-slate-200 hover:border-[#1E3A5F]/35 hover:shadow-sm transition-all text-left group">
              <div className="w-11 h-11 sm:w-12 sm:h-12 rounded-xl bg-[#1E3A5F] text-white flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                <BotMessageSquare className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <div className="font-semibold text-slate-900 mb-0.5">进入 AI 助手</div>
                <div className="text-xs text-slate-500">解释政策口径并辅助准备材料</div>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-[#1E3A5F] transition-colors" />
            </button>
            
            <button onClick={() => onNavigate('ticket')} className="flex items-center gap-3 sm:gap-4 p-4 rounded-2xl bg-white border border-slate-200 hover:border-[#1E3A5F]/35 hover:shadow-sm transition-all text-left group">
              <div className="w-11 h-11 sm:w-12 sm:h-12 rounded-xl bg-[#1E3A5F] text-white flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                <TicketCheck className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <div className="font-semibold text-slate-900 mb-0.5">办理人工协同</div>
                <div className="text-xs text-slate-500">提交疑难问题并跟踪复核处理状态</div>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-[#1E3A5F] transition-colors" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
