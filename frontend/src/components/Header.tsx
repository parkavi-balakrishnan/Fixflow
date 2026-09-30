import React, { useEffect, useState } from 'react';
import { checkBackendHealth } from '../services/api';
import { SparklesIcon, RotateCcwIcon } from './Icons';

interface HeaderProps {
  onReset?: () => void;
  isResultActive?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onReset, isResultActive }) => {
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let isMounted = true;
    checkBackendHealth()
      .then(() => {
        if (isMounted) setBackendOnline(true);
      })
      .catch(() => {
        if (isMounted) setBackendOnline(false);
      });

    const interval = setInterval(() => {
      checkBackendHealth()
        .then(() => {
          if (isMounted) setBackendOnline(true);
        })
        .catch(() => {
          if (isMounted) setBackendOnline(false);
        });
    }, 25000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl transition-all">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3.5 sm:px-6">
        {/* Brand / Logo */}
        <button
          type="button"
          onClick={onReset}
          className="group flex items-center gap-3 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 rounded-xl p-1 transition-opacity hover:opacity-95"
          aria-label="FixFlow Home - Reset to start"
        >
          {/* Futuristic icon symbol */}
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400 via-sky-500 to-blue-600 p-[1.5px] shadow-lg shadow-cyan-500/20">
            <div className="flex h-full w-full items-center justify-center rounded-[10px] bg-slate-950 transition-colors group-hover:bg-slate-900">
              <SparklesIcon size={18} className="text-cyan-400 transition-transform group-hover:scale-110 duration-300" />
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-extrabold tracking-tight text-white font-sans">
                Fix<span className="galaxy-text-gradient">Flow</span>
              </span>
              <span className="hidden sm:inline-flex items-center rounded-full bg-cyan-950/80 px-2 py-0.5 text-[10px] font-semibold text-cyan-300 ring-1 ring-inset ring-cyan-500/30 font-mono">
                PRISM AI
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden xs:block">
              Smart Guided Troubleshooting
            </p>
          </div>
        </button>

        {/* Right side status & actions */}
        <div className="flex items-center gap-3">
          {/* Reset / New Diagnosis action */}
          {isResultActive && (
            <button
              type="button"
              onClick={onReset}
              className="flex items-center gap-1.5 rounded-xl border border-slate-700/80 bg-slate-900/80 px-3.5 py-1.5 text-xs font-semibold text-slate-200 hover:border-slate-600 hover:bg-slate-800 hover:text-white transition-all shadow-sm active:scale-95"
            >
              <RotateCcwIcon size={13} />
              <span>New Diagnosis</span>
            </button>
          )}

          {/* Engine Status indicator */}
          <div className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-400">
            <span
              className={`h-2 w-2 rounded-full ${
                backendOnline === true
                  ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50 animate-pulse'
                  : backendOnline === false
                  ? 'bg-amber-400'
                  : 'bg-slate-500'
              }`}
            />
            <span className="hidden sm:inline text-slate-300 font-medium">
              {backendOnline === true
                ? 'FastAPI Engine Active'
                : backendOnline === false
                ? 'Connecting to Engine...'
                : 'Engine Ready'}
            </span>
            <span className="sm:hidden text-slate-300 font-medium text-[11px]">
              {backendOnline === true ? 'Active' : 'Standby'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
