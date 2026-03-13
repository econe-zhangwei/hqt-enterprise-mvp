import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/Card';
import { api, type MatchData, type MatchResult, type MatchSummary, type PolicyDetail } from '../../services/api';

export default function Match({
  enterpriseId,
  results,
  summary,
  onResults,
  onPolicySelect,
}: {
  enterpriseId: string | null;
  results: MatchResult[];
  summary: MatchSummary;
  onResults: (res: MatchData) => void;
  onPolicySelect: (policyId: string | null) => void;
}) {
  const [selectedPolicy, setSelectedPolicy] = useState<MatchResult | null>(null);
  const [detail, setDetail] = useState<PolicyDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (enterpriseId && results.length === 0) {
      void loadMatch();
    }
  }, [enterpriseId, results.length]);

  useEffect(() => {
    if (results.length === 0) {
      setSelectedPolicy(null);
      setDetail(null);
      onPolicySelect(null);
      return;
    }

    const active = selectedPolicy && results.find((item) => item.policy_id === selectedPolicy.policy_id);
    const nextPolicy = active || results[0];
    setSelectedPolicy(nextPolicy);
    void loadPolicyDetail(nextPolicy);
  }, [results]);

  const loadMatch = async () => {
    setIsLoading(true);
    setMessage('');
    try {
      if (!enterpriseId) return;
      const taskRes = await api.runMatch(enterpriseId);
      const res = await api.getMatchResults(taskRes.task_id);
      onResults(res);
    } catch (err: any) {
      setMessage(err.message || '匹配失败');
    } finally {
      setIsLoading(false);
    }
  };

  const loadPolicyDetail = async (policy: MatchResult) => {
    onPolicySelect(policy.policy_id);
    setIsDetailLoading(true);
    try {
      const res = await api.getPolicyDetail(policy.policy_id);
      setDetail(res);
    } catch (err) {
      console.error(err);
    } finally {
      setIsDetailLoading(false);
    }
  };

  const handleSelectPolicy = async (policy: MatchResult) => {
    setSelectedPolicy(policy);
    await loadPolicyDetail(policy);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6 lg:min-h-[calc(100vh-16rem)]">
      {/* Left List */}
      <Card className="flex flex-col overflow-hidden lg:min-h-[calc(100vh-16rem)]">
        <CardHeader className="shrink-0">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>匹配结果</CardTitle>
              <CardDescription>优先浏览政策标题、状态、得分和下一步动作。</CardDescription>
            </div>
            <span className="w-fit px-3 py-1 rounded-full bg-[#EEF4FA] text-[#1E3A5F] text-xs font-semibold border border-[#D4E0EC]">
              结果列表
            </span>
          </div>
        </CardHeader>
        <CardContent className="flex-1 lg:overflow-y-auto space-y-4">
          {isLoading ? (
            <div className="flex items-center justify-center h-40 text-slate-400">正在匹配中...</div>
          ) : !enterpriseId ? (
            <div className="flex items-center justify-center h-40 text-slate-400 bg-slate-50 rounded-xl border border-slate-100">请先在企业信息页保存画像。</div>
          ) : message ? (
            <div className="flex items-center justify-center h-40 text-slate-500 bg-slate-50 rounded-xl border border-slate-100">{message}</div>
          ) : results.length === 0 ? (
            <div className="flex items-center justify-center h-40 text-slate-400 bg-slate-50 rounded-xl border border-slate-100">暂无匹配结果。</div>
          ) : (
            <>
              <div className="text-sm font-medium text-slate-700 mb-4 bg-slate-50 p-3 rounded-lg border border-slate-100">
                可申报 {summary.eligible_count}，需完善 {summary.potential_count}
              </div>
              <div className="space-y-4">
                {results.map((item, i) => (
                  <div 
                    key={i} 
                    className={`p-5 rounded-2xl border transition-all cursor-pointer ${selectedPolicy?.policy_id === item.policy_id ? 'border-[#1E3A5F] bg-[#F5F9FD] shadow-sm' : 'border-slate-200 bg-white hover:border-[#1E3A5F]/35'}`}
                    onClick={() => handleSelectPolicy(item)}
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-3">
                      <h4 className="font-semibold text-slate-900 leading-tight">{item.policy_title}</h4>
                      <div className="flex flex-wrap items-center gap-2 shrink-0">
                        <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${item.eligibility === 'eligible' ? 'bg-[#E5F3EC] text-[#2E8B57]' : 'bg-[#F7E8C9] text-[#A96B10]'}`}>
                          {item.eligibility === 'eligible' ? '可申报' : '需完善'}
                        </span>
                        <span className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-semibold border border-slate-200">
                          {item.score}分
                        </span>
                      </div>
                    </div>
                    
                    <div className="space-y-2 text-sm">
                      <div className="flex gap-2">
                        <span className="text-slate-500 shrink-0">下一步：</span>
                        <span className="text-slate-900 font-medium">{item.next_action === 'prepare_materials' ? '准备申报材料' : '补齐条件后再评估'}</span>
                      </div>
                      <div className="flex gap-2">
                        <span className="text-slate-500 shrink-0">命中原因：</span>
                        <span className="text-slate-700">{item.reasons?.join('；') || '无'}</span>
                      </div>
                      {item.missing_items?.length > 0 && (
                        <div className="flex gap-2">
                          <span className="text-slate-500 shrink-0">缺口项：</span>
                          <span className="text-[#A96B10] font-medium">{item.missing_items.join('；')}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Right Detail */}
      <Card className="flex flex-col overflow-hidden bg-slate-50/70 lg:min-h-[calc(100vh-16rem)]">
        <CardHeader className="shrink-0 bg-white">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>政策详情</CardTitle>
              <CardDescription>在这里展开阅读申报时间、材料和政策原文。</CardDescription>
            </div>
            <span className="w-fit px-3 py-1 rounded-full bg-[#EEF4FA] text-[#1E3A5F] text-xs font-semibold border border-[#D4E0EC]">
              详情面板
            </span>
          </div>
        </CardHeader>
        <CardContent className="flex-1 lg:overflow-y-auto">
          {isDetailLoading ? (
            <div className="flex items-center justify-center h-40 text-slate-400">加载中...</div>
          ) : !detail ? (
            <div className="flex items-center justify-center h-40 text-slate-400">点击左侧政策卡查看详情。</div>
          ) : (
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-semibold text-slate-900 mb-4">{detail.title}</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                  <div className="p-3 rounded-xl bg-white border border-slate-200">
                    <span className="text-slate-500 block mb-1">支持方式</span>
                    <span className="font-medium text-slate-900">{detail.support_type}</span>
                  </div>
                  <div className="p-3 rounded-xl bg-white border border-slate-200">
                    <span className="text-slate-500 block mb-1">区域 / 层级</span>
                    <span className="font-medium text-slate-900">{detail.region_code} / {detail.level === 'city' ? '市级' : '区级'}</span>
                  </div>
                  <div className="p-3 rounded-xl bg-white border border-slate-200 sm:col-span-2">
                    <span className="text-slate-500 block mb-1">生效时间</span>
                    <span className="font-medium text-slate-900">{detail.effective_from} ~ {detail.effective_to || '长期'}</span>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-semibold text-slate-900">所需材料</h4>
                <div className="flex flex-wrap gap-2">
                  {detail.required_materials?.map((m: string, i: number) => (
                    <span key={i} className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-sm border border-slate-200">
                      {m}
                    </span>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-semibold text-slate-900">政策大纲</h4>
                <div className="space-y-3">
                  {detail.outline_sections?.map((sec: any, i: number) => (
                    <div key={i} className="p-4 rounded-xl bg-white border border-slate-200">
                      <h5 className="font-medium text-slate-900 mb-2">{sec.title}</h5>
                      <ul className="list-disc list-inside text-sm text-slate-600 space-y-1">
                        {sec.items?.map((item: string, j: number) => (
                          <li key={j}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>

              {detail.source_url && (
                <div className="pt-4 border-t border-slate-200">
                  <a href={detail.source_url} target="_blank" rel="noreferrer" className="text-sm text-[#1E3A5F] hover:text-[#17304f] hover:underline font-medium">
                    查看政策原文 →
                  </a>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
