import { useState, useEffect } from 'react';
import Login from './pages/Login';
import Workspace from './pages/Workspace';
import type { LoginSession } from './services/api';

export default function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('hqt_token'));
  const [subject, setSubject] = useState<string | null>(localStorage.getItem('hqt_user'));

  useEffect(() => {
    if (token) {
      localStorage.setItem('hqt_token', token);
    } else {
      localStorage.removeItem('hqt_token');
      localStorage.removeItem('hqt_user');
      localStorage.removeItem('hqt_enterprise_id');
    }
  }, [token]);

  useEffect(() => {
    if (subject) {
      localStorage.setItem('hqt_user', subject);
    }
  }, [subject]);

  useEffect(() => {
    const html = document.documentElement;
    const body = document.body;

    const applyBaseTypography = () => {
      html.style.setProperty('font-size', '16px', 'important');
      html.style.setProperty(
        'font-family',
        'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        'important',
      );
      html.style.setProperty('-webkit-text-size-adjust', '100%', 'important');
      html.style.setProperty('text-size-adjust', '100%', 'important');

      body.style.setProperty('font-size', '16px', 'important');
      body.style.setProperty(
        'font-family',
        'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        'important',
      );
    };

    applyBaseTypography();

    const observer = new MutationObserver(() => {
      applyBaseTypography();
    });

    observer.observe(html, {
      attributes: true,
      attributeFilter: ['class', 'style'],
    });

    observer.observe(body, {
      attributes: true,
      attributeFilter: ['class', 'style'],
    });

    return () => observer.disconnect();
  }, []);

  const handleLogin = (session: LoginSession) => {
    localStorage.setItem('hqt_token', session.token);
    localStorage.setItem('hqt_user', session.subject);
    setToken(session.token);
    setSubject(session.subject);
  };

  const handleLogout = () => {
    localStorage.removeItem('hqt_token');
    localStorage.removeItem('hqt_user');
    localStorage.removeItem('hqt_enterprise_id');
    setSubject(null);
    setToken(null);
  };

  if (!token) {
    return <Login onLogin={handleLogin} />;
  }

  return <Workspace user={subject} onLogout={handleLogout} />;
}
