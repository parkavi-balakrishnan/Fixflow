import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { TroubleshootingForm } from './components/TroubleshootingForm';
import { LoadingState } from './components/LoadingState';
import { TroubleshootingResult } from './components/TroubleshootingResult';
import { ErrorState } from './components/ErrorState';
import { troubleshoot } from './services/api';
import type { FixFlowError, TroubleshootingResultData } from './types/fixflow';
import { SparklesIcon, ZapIcon } from './components/Icons';

type AppState = 'idle' | 'loading' | 'success' | 'error';

export const App: React.FC = () => {
  const [state, setState] = useState<AppState>('idle');
  const [lastParams, setLastParams] = useState<{
    query: string;
    device?: string;
    model?: string;
  } | null>(null);
  const [resultData, setResultData] = useState<TroubleshootingResultData | null>(null);
  const [error, setError] = useState<FixFlowError | null>(null);

  const handleSubmit = useCallback(async (params: {
    query: string;
    device?: string;
    model?: string;
  }) => {
    setLastParams(params);
    setState('loading');
    setError(null);

    try {
      const data = await troubleshoot({
        query: params.query,
        device: params.device,
        model: params.model,
      });
      setResultData(data);
      setState('success');
    } catch (err: unknown) {
      const fixFlowErr = err as FixFlowError;
      setError(
        fixFlowErr.type
          ? fixFlowErr
          : {
              type: 'unknown',
              title: 'Diagnostics Service Interrupted',
              message: err instanceof Error ? err.message : 'Please check your connection and try again.',
            }
      );
      setState('error');
    }
  }, []);

  const handleRetry = () => {
    if (lastParams) {
      handleSubmit(lastParams);
    } else {
      handleReset();
    }
  };

  const handleReset = useCallback(() => {
    setState('idle');
    setError(null);
  }, []);

  // Global keyboard shortcuts: Esc to reset
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && state !== 'idle') {
        handleReset();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [state, handleReset]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500/20 selection:text-cyan-200">
      {/* Background ambient lighting gradients */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-gradient-to-b from-cyan-500/10 via-blue-600/5 to-transparent blur-3xl rounded-full" />
        <div className="absolute top-1/4 -right-40 w-[500px] h-[500px] bg-indigo-500/5 blur-3xl rounded-full" />
        <div className="absolute bottom-10 -left-40 w-[500px] h-[500px] bg-cyan-600/5 blur-3xl rounded-full" />
      </div>

      {/* Persistent Navigation Header */}
      <Header onReset={handleReset} isResultActive={state !== 'idle'} />

      {/* Main Content Area */}
      <main className="relative z-10 flex-1 px-4 sm:px-6 py-8 sm:py-12 max-w-6xl mx-auto w-full flex flex-col justify-center">
        {state === 'idle' && (
          <TroubleshootingForm onSubmit={handleSubmit} isLoading={false} />
        )}

        {state === 'loading' && lastParams && (
          <LoadingState
            query={lastParams.query}
            device={lastParams.device}
            model={lastParams.model}
          />
        )}

        {state === 'success' && resultData && (
          <TroubleshootingResult data={resultData} onReset={handleReset} />
        )}

        {state === 'error' && error && (
          <ErrorState
            error={error}
            onRetry={lastParams ? handleRetry : undefined}
            onReset={handleReset}
          />
        )}
      </main>

      {/* Modern Hackathon Footer */}
      <footer className="relative z-10 border-t border-slate-900 bg-slate-950/80 py-6 text-xs text-slate-400 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <SparklesIcon size={14} className="text-cyan-400" />
            <p className="text-slate-400">
              FixFlow • Smart Guided Troubleshooting • Samsung PRISM Hackathon 2026
            </p>
          </div>
          <div className="flex items-center gap-3 text-slate-400 font-mono text-[11px]">
            <span className="flex items-center gap-1 text-cyan-300">
              <ZapIcon size={11} />
              FastPath Cache
            </span>
            <span>•</span>
            <span>Hybrid RAG</span>
            <span>•</span>
            <span>One UI Deeplinks</span>
            <span>•</span>
            <span>Gate G2/G5 Clean</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;