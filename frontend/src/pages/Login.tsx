import { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { api, type LoginSession } from '../services/api';
import { Building2, ShieldCheck, Sparkles } from 'lucide-react';

export default function Login({ onLogin }: { onLogin: (session: LoginSession) => void }) {
  const [username, setUsername] = useState('enterprise');
  const [password, setPassword] = useState('123456');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const pageRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const root = pageRef.current;
    if (!root) return;

    const forceStyle = (
      elements: NodeListOf<HTMLElement> | HTMLElement[],
      styles: Record<string, string>,
    ) => {
      for (const element of elements) {
        for (const [property, value] of Object.entries(styles)) {
          element.style.setProperty(property, value, 'important');
        }
      }
    };

    const applyIsolation = () => {
      forceStyle([root], {
        'font-size': '16px',
        'line-height': '24px',
        'font-family':
          'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      });

      forceStyle(root.querySelectorAll<HTMLElement>('h1, h2, h3, p, span, label'), {
        'font-family':
          'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      });

      forceStyle(root.querySelectorAll<HTMLElement>('input'), {
        'font-size': '16px',
        'line-height': '24px',
        'padding-top': '8px',
        'padding-bottom': '8px',
        'font-family':
          'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      });

      forceStyle(root.querySelectorAll<HTMLElement>('button'), {
        'font-family':
          'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      });

      forceStyle(root.querySelectorAll<HTMLElement>('[data-login-submit]'), {
        'font-size': '16px',
        'line-height': '24px',
      });
    };

    applyIsolation();

    const observer = new MutationObserver(() => {
      applyIsolation();
    });

    observer.observe(root, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class', 'style'],
    });

    return () => observer.disconnect();
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    try {
      const session = await api.login(username, password);
      onLogin(session);
    } catch (err: any) {
      setError(err.message || '登录失败');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div ref={pageRef} data-login-page className="min-h-screen flex bg-slate-100">
      {/* Left side - Visual/Branding */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden bg-[#1E3A5F] p-12 flex-col justify-between">
        <div className="absolute inset-0 z-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_0%_0%,_rgba(255,255,255,0.16)_0%,_transparent_45%)]" />
          <div className="absolute bottom-0 right-0 w-full h-full bg-[radial-gradient(circle_at_100%_100%,_rgba(255,255,255,0.08)_0%,_transparent_50%)]" />
        </div>
        
        <div className="relative z-10">
          <div className="flex items-center gap-2 text-white mb-16">
            <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center backdrop-blur-md border border-white/15">
              <Building2 className="w-5 h-5" />
            </div>
            <span className="font-semibold text-xl tracking-tight">惠企通</span>
          </div>
          
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="max-w-md"
          >
            <h1 className="text-4xl md:text-5xl font-medium text-white leading-tight mb-6">
              政策服务办理<br />
              <span className="text-slate-200/80">业务工作台</span>
            </h1>
            <p className="text-slate-200/80 text-lg leading-relaxed mb-12">
              面向企业服务与政策办理场景，统一管理企业画像、匹配结果、政策解读和人工协同流程。
            </p>
            
            <div className="space-y-6">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-full bg-white/8 flex items-center justify-center shrink-0 border border-white/10">
                  <ShieldCheck className="w-5 h-5 text-slate-200" />
                </div>
                <div>
                  <h3 className="text-white font-medium mb-1">精准匹配可解释</h3>
                  <p className="text-slate-300/70 text-sm">围绕政策条件、命中原因和缺口项形成清晰结果说明。</p>
                </div>
              </div>
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-full bg-white/8 flex items-center justify-center shrink-0 border border-white/10">
                  <Sparkles className="w-5 h-5 text-slate-200" />
                </div>
                <div>
                  <h3 className="text-white font-medium mb-1">AI 助手深度解读</h3>
                  <p className="text-slate-300/70 text-sm">针对具体政策条件，辅助解释办理口径与材料准备要求。</p>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
        
        <div className="relative z-10 text-slate-300/60 text-sm">
          &copy; 2026 惠企通企业服务平台
        </div>
      </div>

      {/* Right side - Login Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 sm:p-12">
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-md"
          data-login-card
        >
          <div className="lg:hidden flex items-center gap-2 text-slate-900 mb-12">
            <div className="w-8 h-8 rounded-lg bg-[#1E3A5F] flex items-center justify-center">
              <Building2 className="w-5 h-5 text-white" />
            </div>
            <span className="font-semibold text-xl tracking-tight">惠企通</span>
          </div>

          <div className="mb-10">
            <h2 className="text-3xl font-semibold text-slate-900 tracking-tight mb-2">欢迎登录</h2>
            <p className="text-slate-500">进入企业政策服务办理工作台</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-6" data-login-form>
            <Input 
              label="用户名" 
              placeholder="请输入用户名" 
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
            <Input 
              label="密码" 
              type="password" 
              placeholder="请输入密码" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            
            {error && (
              <div className="p-3 rounded-xl bg-red-50 border border-red-100 text-red-600 text-sm">
                {error}
              </div>
            )}

            <Button type="submit" className="w-full" size="lg" isLoading={isLoading} data-login-submit>
              进入工作台
            </Button>
            
            <div className="text-center">
              <p className="text-sm text-zinc-500">
                开发环境默认账号：<span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-700">enterprise</span> / <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-700">123456</span>
              </p>
            </div>
          </form>
        </motion.div>
      </div>
    </div>
  );
}
