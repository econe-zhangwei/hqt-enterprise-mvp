import { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { api } from '../../services/api';
import { BotMessageSquare, User, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

export default function Assistant({ enterpriseId, topPolicyId, onHandoff }: { enterpriseId: string | null, topPolicyId: string | null, onHandoff: () => void }) {
  const [messages, setMessages] = useState<{ role: 'user' | 'ai', content: string }[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [handoffReason, setHandoffReason] = useState<string | null>(null);
  const [lastExchange, setLastExchange] = useState<{ question: string; answer: string } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!input.trim() || !enterpriseId) return;
    
    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsLoading(true);
    setHandoffReason(null);

    try {
      const res = await api.askAI({
        enterprise_id: enterpriseId,
        question: userMsg,
        context_policy_id: topPolicyId,
      });
      setMessages(prev => [...prev, { role: 'ai', content: res.answer }]);
      setLastExchange({ question: userMsg, answer: res.answer });
      if (res.recommend_handoff) {
        setHandoffReason(res.handoff_reason);
      }
    } catch (err: any) {
      setMessages(prev => [...prev, { role: 'ai', content: `请求失败：${err.message || '未知错误'}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleHandoff = async () => {
    if (!enterpriseId || !lastExchange) return;
    try {
      await api.handoffTicket({
        enterprise_id: enterpriseId,
        question: lastExchange.question,
        answer: lastExchange.answer,
        context_policy_id: topPolicyId,
        handoff_reason: handoffReason,
      });
      onHandoff();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1280px]">
      <Card className="flex min-h-[70dvh] flex-col overflow-hidden lg:min-h-[calc(100vh-16rem)]">
        <CardHeader className="shrink-0">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>AI 政策助手</CardTitle>
              <CardDescription>围绕当前企业画像和已选政策做解释与追问。</CardDescription>
            </div>
            <span className="w-fit px-3 py-1 rounded-full bg-[#EEF4FA] text-[#1E3A5F] text-xs font-semibold border border-[#D4E0EC] flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5" />
              智能问答
            </span>
          </div>
        </CardHeader>
        
        <CardContent className="flex-1 flex flex-col p-0 overflow-hidden bg-slate-50/70">
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 sm:space-y-6">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-4">
                <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center border border-slate-200">
                  <BotMessageSquare className="w-8 h-8 text-slate-300" />
                </div>
                <p>你好，我是你的政策助手。你可以问我关于政策条件、材料准备等问题。</p>
              </div>
            ) : (
              <AnimatePresence initial={false}>
                {messages.map((msg, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex gap-3 sm:gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                  >
                    <div className={`w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center shrink-0 border ${msg.role === 'user' ? 'bg-[#1E3A5F] text-white border-[#17304f]' : 'bg-white text-slate-600 border-slate-200 shadow-sm'}`}>
                      {msg.role === 'user' ? <User className="w-5 h-5" /> : <BotMessageSquare className="w-5 h-5" />}
                    </div>
                    <div className={`max-w-[88%] sm:max-w-[80%] rounded-2xl p-3.5 sm:p-4 text-sm leading-relaxed break-words ${msg.role === 'user' ? 'bg-[#1E3A5F] text-white' : 'bg-white text-slate-700 border border-slate-200 shadow-sm'}`}>
                      {msg.content}
                    </div>
                  </motion.div>
                ))}
                {isLoading && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex gap-3 sm:gap-4"
                  >
                    <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-white text-slate-600 border border-slate-200 shadow-sm flex items-center justify-center shrink-0">
                      <BotMessageSquare className="w-5 h-5" />
                    </div>
                    <div className="max-w-[88%] sm:max-w-[80%] rounded-2xl p-3.5 sm:p-4 bg-white border border-slate-200 shadow-sm flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-slate-300 animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-2 h-2 rounded-full bg-slate-300 animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-2 h-2 rounded-full bg-slate-300 animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="p-4 sm:p-6 bg-white border-t border-slate-100 shrink-0">
            {handoffReason && (
              <div className="mb-4 p-4 rounded-xl bg-[#FFF8EC] border border-[#F0DFC0] flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h4 className="text-sm font-medium text-[#8A5A12] mb-1">建议转人工复核</h4>
                  <p className="text-xs text-[#9B6D22]">{handoffReason}</p>
                </div>
                <Button variant="secondary" size="sm" onClick={handleHandoff} className="shrink-0 bg-white border-[#E5CFA6] text-[#8A5A12] hover:bg-[#FFF8EC]">
                  一键转人工
                </Button>
              </div>
            )}
            
            <div className="flex flex-col sm:flex-row gap-3">
              <Input 
                className="flex-1" 
                placeholder="例如：这条政策我还缺什么材料？" 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                disabled={isLoading || !enterpriseId}
              />
              <Button onClick={handleSend} isLoading={isLoading} disabled={!enterpriseId || !input.trim()} className="w-full sm:w-auto">
                发送
              </Button>
            </div>
            {!enterpriseId && (
              <p className="text-xs text-slate-500 mt-2">请先在企业信息页保存画像。</p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
