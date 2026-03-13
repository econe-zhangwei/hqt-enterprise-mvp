import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { api } from '../../services/api';
import { TicketCheck, Clock, MessageSquare } from 'lucide-react';

export default function Ticket({ enterpriseId }: { enterpriseId: string | null }) {
  const [desc, setDesc] = useState('');
  const [callbackTime, setCallbackTime] = useState('');
  const [ticketId, setTicketId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [contactMobile, setContactMobile] = useState('');

  useEffect(() => {
    if (!enterpriseId) {
      setContactMobile('');
      return;
    }

    let cancelled = false;
    api
      .getEnterpriseProfile(enterpriseId)
      .then((profile) => {
        if (!cancelled) {
          setContactMobile(profile.contact_mobile);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMessage('未获取到企业联系人，请先在企业信息页保存画像。');
        }
      });

    return () => {
      cancelled = true;
    };
  }, [enterpriseId]);

  const handleCreate = async () => {
    if (!enterpriseId || !contactMobile) return;
    setIsLoading(true);
    setMessage('正在提交...');
    try {
      const res = await api.createTicket({
        enterprise_id: enterpriseId,
        issue_type: 'eligibility_consult',
        description: desc,
        contact_mobile: contactMobile,
        callback_time: callbackTime || null,
      });
      setTicketId(res.ticket_id);
      setStatus(res.status);
      setMessage(`工单已创建：${res.ticket_id}，状态：${res.status}`);
      setDesc('');
      setCallbackTime('');
    } catch (err: any) {
      setMessage(err.message || '提交失败');
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuery = async () => {
    if (!ticketId) {
      setMessage('暂无工单，请先提交。');
      return;
    }
    setIsLoading(true);
    try {
      const res = await api.queryTicket(ticketId);
      setStatus(res.status);
      setLogs(res.logs || []);
      setMessage(`查询成功，当前状态：${res.status}`);
    } catch (err: any) {
      setMessage(err.message || '查询失败');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1280px] space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>工单提交与查询</CardTitle>
              <CardDescription>当政策条件需要人工确认时，在这里发起顾问协助。</CardDescription>
            </div>
            <span className="w-fit px-3 py-1 rounded-full bg-[#EEF4FA] text-[#1E3A5F] text-xs font-semibold border border-[#D4E0EC] flex items-center gap-1">
              <TicketCheck className="w-3.5 h-3.5" />
              人工协同
            </span>
          </div>
        </CardHeader>
        <CardContent className="space-y-8">
          {!enterpriseId ? (
              <div className="flex items-center justify-center h-40 text-slate-400 bg-slate-50 rounded-xl border border-slate-100">
                请先在企业信息页保存画像。
              </div>
          ) : (
            <>
              <div className="space-y-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-slate-700">问题描述</label>
                  <textarea 
                    className="flex min-h-[120px] w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-base sm:text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1E3A5F]/15 focus:border-[#1E3A5F] resize-none"
                    placeholder="请描述你需要顾问协助的内容"
                    value={desc}
                    onChange={(e) => setDesc(e.target.value)}
                  />
                </div>
                <Input 
                  label="预约联系时间（可选）" 
                  placeholder="例如：2026-03-05 10:00" 
                  value={callbackTime}
                  onChange={(e) => setCallbackTime(e.target.value)}
                />
              </div>

              <div className="flex flex-col sm:flex-row gap-3 pt-4 border-t border-slate-100">
                <Button onClick={handleCreate} isLoading={isLoading} disabled={!desc.trim()} className="flex-1 sm:flex-none">
                  提交工单
                </Button>
                <Button variant="secondary" onClick={handleQuery} isLoading={isLoading} disabled={!ticketId} className="flex-1 sm:flex-none">
                  查询最新状态
                </Button>
              </div>
              
              {message && (
                <div className="text-sm text-slate-500 bg-slate-50 p-4 rounded-xl border border-slate-100 flex items-start gap-3">
                  <MessageSquare className="w-5 h-5 text-slate-400 shrink-0" />
                  <div>{message}</div>
                </div>
              )}

              {ticketId && (
                <div className="mt-8 pt-8 border-t border-slate-100">
                  <h4 className="text-lg font-semibold text-slate-900 mb-4">工单跟踪</h4>
                  <div className="space-y-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between p-4 rounded-xl bg-slate-50 border border-slate-100">
                      <div>
                        <div className="text-sm text-slate-500 mb-1">工单编号</div>
                        <div className="font-mono text-slate-900 font-medium">{ticketId}</div>
                      </div>
                      <div className="sm:text-right">
                        <div className="text-sm text-slate-500 mb-1">当前状态</div>
                        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#E3ECF7] text-[#1E3A5F] text-xs font-semibold">
                          <Clock className="w-3.5 h-3.5" />
                          {status}
                        </div>
                      </div>
                    </div>

                    {logs.length > 0 && (
                      <div className="space-y-3">
                        <h5 className="text-sm font-medium text-slate-700">处理记录</h5>
                        {logs.map((log, i) => (
                          <div key={i} className="p-4 rounded-xl bg-white border border-slate-200 shadow-sm text-sm text-slate-600">
                            {log.message}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
