import React from 'react';
import type { FixFlowError } from '../types/fixflow';
import { AlertTriangleIcon, RotateCcwIcon, ZapIcon } from './Icons';

interface ErrorStateProps {
  error: FixFlowError;
  onRetry?: () => void;
  onReset: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  error,
  onRetry,
  onReset,
}) => {
  const isNetwork = error.type === 'network';

  return (
    <div
      role="alert"
      className="mx-auto w-full max-w-xl text-center py-10 px-4 animate-in fade-in duration-300"
    >
      {/* Icon Badge */}
      <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-3xl border border-rose-500/30 bg-rose-950/30 text-rose-400 shadow-xl shadow-rose-950/20">
        <AlertTriangleIcon size={36} />
      </div>

      <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white mb-2 font-sans">
        {error.title}
      </h2>

      <p className="text-sm sm:text-base text-slate-300 max-w-md mx-auto leading-relaxed mb-4">
        {error.message}
      </p>

      {error.detail && (
        <div className="mx-auto max-w-md rounded-2xl border border-slate-800 bg-slate-950/80 p-3.5 text-xs text-slate-400 font-mono text-left mb-6 break-words shadow-inner">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">
            Engine Diagnostics Detail:
          </span>
          {error.detail}
        </div>
      )}

      {isNetwork && (
        <div className="mx-auto max-w-md rounded-xl border border-cyan-500/20 bg-cyan-950/20 p-3 text-xs text-cyan-300 text-left mb-6 flex items-start gap-2">
          <ZapIcon size={16} className="text-cyan-400 mt-0.5 flex-shrink-0" />
          <span>
            <strong>Troubleshooting Tip:</strong> Ensure the FastAPI server is running with <code className="rounded bg-slate-900 px-1.5 py-0.5 font-mono text-white">uvicorn src.api:app --host 127.0.0.1 --port 8000</code>.
          </span>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center justify-center gap-3">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-5 py-2.5 text-xs sm:text-sm font-semibold text-white shadow-md shadow-cyan-500/20 hover:from-cyan-400 hover:to-blue-500 transition-all active:scale-95"
          >
            <RotateCcwIcon size={14} />
            <span>Try Again</span>
          </button>
        )}

        <button
          type="button"
          onClick={onReset}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 px-5 py-2.5 text-xs sm:text-sm font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition-all active:scale-95"
        >
          <span>Modify Query</span>
        </button>
      </div>
    </div>
  );
};
