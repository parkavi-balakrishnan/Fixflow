import React, { useState } from 'react';
import type { Deeplink, ValidationDeepLink } from '../types/fixflow';
import { SettingsIcon, CheckCircleIcon, CopyIcon, ExternalLinkIcon, ShieldCheckIcon } from './Icons';

interface DeeplinkModalProps {
  deeplink: Deeplink;
  validationDeeplink?: ValidationDeepLink | null;
  actionTitle: string;
  onClose: () => void;
}

export const DeeplinkModal: React.FC<DeeplinkModalProps> = ({
  deeplink,
  validationDeeplink,
  actionTitle,
  onClose,
}) => {
  const [copied, setCopied] = useState(false);
  const [simulatedSettingState, setSimulatedSettingState] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(deeplink.deeplink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleLaunch = () => {
    try {
      window.location.href = deeplink.deeplink;
    } catch {
      // Ignored on desktop browser
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
      <div
        className="relative w-full max-w-lg rounded-2xl border border-slate-700/80 bg-slate-900 p-6 sm:p-7 shadow-2xl shadow-cyan-950/40"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          aria-label="Close settings simulator"
        >
          ✕
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3 mb-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-md">
            <SettingsIcon size={20} />
          </div>
          <div>
            <span className="text-[11px] font-mono uppercase tracking-wider text-cyan-400 font-semibold">
              Samsung One UI Intent Simulator
            </span>
            <h3 id="modal-title" className="text-lg font-bold text-white font-sans">
              {actionTitle}
            </h3>
          </div>
        </div>

        {/* Simulated One UI Device Screen Card */}
        <div className="rounded-xl border border-slate-800 bg-slate-950/90 p-4 mb-5 shadow-inner">
          <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/80 text-xs text-slate-400">
            <span className="font-semibold text-slate-200">One UI Settings Preview</span>
            <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300 font-mono">
              Samsung Galaxy System
            </span>
          </div>

          {/* Setting Row with Interactive Toggle */}
          <div className="flex items-center justify-between py-2">
            <div className="pr-4">
              <span className="block text-sm font-semibold text-white">
                {deeplink.message || 'System Preference'}
              </span>
              <span className="text-xs text-slate-400 line-clamp-2">
                {deeplink.description}
              </span>
            </div>

            {/* Interactive Toggle switch */}
            <button
              type="button"
              onClick={() => setSimulatedSettingState(!simulatedSettingState)}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                simulatedSettingState ? 'bg-cyan-500' : 'bg-slate-700'
              }`}
              role="switch"
              aria-checked={simulatedSettingState}
              title="Click to simulate toggle in One UI"
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  simulatedSettingState ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* Validation Rule Card if present */}
          {validationDeeplink && (
            <div className="mt-3 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
              <div className="flex items-center gap-2">
                <ShieldCheckIcon size={14} className="text-emerald-400" />
                <span className="text-slate-300 font-medium">Automated Verification:</span>
              </div>
              <span className="font-mono text-cyan-300 text-[11px]">
                {validationDeeplink.key} {validationDeeplink.condition === 'equal' ? '==' : validationDeeplink.condition} {validationDeeplink.value}
              </span>
            </div>
          )}
        </div>

        {/* Protocol URI Display */}
        <div className="mb-6">
          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
            Samsung Intent Deeplink Protocol
          </label>
          <div className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5">
            <span className="flex-1 font-mono text-xs text-cyan-300 truncate select-all">
              {deeplink.deeplink}
            </span>
            <button
              type="button"
              onClick={handleCopy}
              className="flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs text-slate-200 hover:text-white hover:bg-slate-700 transition-colors"
            >
              {copied ? (
                <>
                  <CheckCircleIcon size={13} className="text-emerald-400" />
                  <span className="text-emerald-400 font-medium">Copied</span>
                </>
              ) : (
                <>
                  <CopyIcon size={13} />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-700 bg-slate-800/80 px-4 py-2 text-xs sm:text-sm font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
          >
            Close
          </button>
          <button
            type="button"
            onClick={handleLaunch}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-2 text-xs sm:text-sm font-semibold text-white shadow-md shadow-cyan-500/20 hover:from-cyan-400 hover:to-blue-500 transition-all active:scale-95"
          >
            <ExternalLinkIcon size={14} />
            <span>Launch on Device</span>
          </button>
        </div>
      </div>
    </div>
  );
};
