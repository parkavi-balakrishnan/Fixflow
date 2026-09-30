import React, { useEffect, useState } from 'react';
import { SparklesIcon, ZapIcon, PhoneIcon } from './Icons';

interface LoadingStateProps {
  query: string;
  device?: string;
  model?: string;
}

const LOADING_STAGES = [
  { text: 'Analyzing symptom semantics with embeddings...', icon: '🧠', tag: 'FastPath Semantic Cache' },
  { text: 'Querying SIIS knowledge base & BM25 hybrid index...', icon: '🔍', tag: 'Hybrid Retrieval' },
  { text: 'Mapping device form factor and settings hierarchy...', icon: '📱', tag: 'Device Context' },
  { text: 'Extracting verified Samsung One UI Settings deeplinks...', icon: '🔗', tag: 'Deeplink Extraction' },
  { text: 'Enforcing Gate G2 schemas and Gate G5 URL leak protection...', icon: '🛡️', tag: 'PRISM Security Gate' },
];

export const LoadingState: React.FC<LoadingStateProps> = ({
  query,
  device,
  model,
}) => {
  const [currentStageIndex, setCurrentStageIndex] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const stageInterval = setInterval(() => {
      setCurrentStageIndex((prev) => (prev + 1) % LOADING_STAGES.length);
    }, 1500);

    const timerInterval = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    return () => {
      clearInterval(stageInterval);
      clearInterval(timerInterval);
    };
  }, []);

  const activeStage = LOADING_STAGES[currentStageIndex];

  return (
    <div
      role="status"
      aria-live="polite"
      className="mx-auto w-full max-w-xl text-center py-10 px-4 animate-in fade-in duration-300"
    >
      {/* Central Visual Pulsing Galaxy AI Orb */}
      <div className="relative mx-auto mb-8 flex h-28 w-28 items-center justify-center">
        {/* Outer glowing pulsing rings */}
        <div className="absolute inset-0 rounded-full bg-cyan-500/10 animate-ping" style={{ animationDuration: '2.5s' }} />
        <div className="absolute -inset-3 rounded-full border border-cyan-500/20 animate-pulse" />
        <div className="absolute -inset-6 rounded-full border border-blue-500/10" />

        {/* Central Glowing Core */}
        <div className="relative flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-tr from-cyan-400 via-sky-500 to-indigo-600 p-[2px] shadow-2xl shadow-cyan-500/30">
          <div className="flex h-full w-full items-center justify-center rounded-[22px] bg-slate-950/80 backdrop-blur-sm">
            <SparklesIcon size={32} className="text-cyan-300 animate-spin" style={{ animationDuration: '8s' }} />
          </div>
        </div>
      </div>

      {/* Dynamic Status Text */}
      <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white mb-2 font-sans">
        Synthesizing Remediation Plan
      </h2>

      {/* Current stage pill */}
      <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-950/40 px-3.5 py-1 text-xs text-cyan-300 font-medium mb-3">
        <span className="text-sm">{activeStage.icon}</span>
        <span className="transition-all duration-300 font-semibold">{activeStage.tag}</span>
        <span className="text-slate-500">•</span>
        <span className="text-slate-400">{elapsedSeconds}s</span>
      </div>

      <p className="text-xs sm:text-sm text-slate-300 min-h-[1.5rem] transition-all duration-300">
        {activeStage.text}
      </p>

      {/* Query in Progress Card */}
      <div className="mt-8 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5 text-left backdrop-blur-xl shadow-lg">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
          <span className="font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <ZapIcon size={12} className="text-cyan-400" />
            Analyzing Query
          </span>
          {(device || model) && (
            <span className="flex items-center gap-1 rounded-md bg-slate-800 px-2 py-0.5 text-[11px] font-mono text-cyan-300">
              <PhoneIcon size={11} />
              {[device, model].filter(Boolean).join(' ')}
            </span>
          )}
        </div>
        <p className="text-xs sm:text-sm text-slate-200 line-clamp-2 italic leading-relaxed">
          "{query}"
        </p>
      </div>
    </div>
  );
};
