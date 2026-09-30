import React, { useState } from 'react';
import type { Action, Deeplink, ValidationDeepLink } from '../types/fixflow';
import { DeeplinkModal } from './DeeplinkModal';
import {
  SettingsIcon,
  ZapIcon,
  CheckCircleIcon,
  CopyIcon,
  AlertTriangleIcon,
  ShieldCheckIcon,
  ExternalLinkIcon,
} from './Icons';

interface TroubleshootingStepProps {
  action: Action;
  index: number;
  isCompleted: boolean;
  onToggleComplete: () => void;
}

export const TroubleshootingStep: React.FC<TroubleshootingStepProps> = ({
  action,
  index,
  isCompleted,
  onToggleComplete,
}) => {
  const [copiedLink, setCopiedLink] = useState<string | null>(null);
  const [showSimulator, setShowSimulator] = useState(false);

  // Formatted step index (01, 02, etc.)
  const stepNumber = String(index + 1).padStart(2, '0');

  // Find the primary actionable deeplink across stepGroups, if any
  const primaryDeeplink: Deeplink | undefined = action.stepGroups.find(
    (sg) => sg.actionableDeeplink?.deeplink
  )?.actionableDeeplink || undefined;

  // Find any validation deeplink
  const primaryValidation: ValidationDeepLink | undefined = action.stepGroups.find(
    (sg) => sg.validationDeeplink?.key
  )?.validationDeeplink || undefined;

  // Category styling
  const category = action.category || 'manual';
  const categoryConfig = {
    auto: {
      label: 'Automated Action',
      badgeClass: 'bg-emerald-950/70 text-emerald-400 border-emerald-500/30 shadow-emerald-950/20',
      icon: <ZapIcon size={12} className="text-emerald-400" />,
      glowBorder: 'hover:border-emerald-500/40',
    },
    manual: {
      label: 'Guided Step',
      badgeClass: 'bg-sky-950/70 text-sky-400 border-sky-500/30 shadow-sky-950/20',
      icon: <SettingsIcon size={12} className="text-sky-400" />,
      glowBorder: 'hover:border-sky-500/40',
    },
    critical: {
      label: 'Service Inspection',
      badgeClass: 'bg-amber-950/70 text-amber-400 border-amber-500/30 shadow-amber-950/20',
      icon: <AlertTriangleIcon size={12} className="text-amber-400" />,
      glowBorder: 'hover:border-amber-500/40',
    },
  }[category];

  const handleCopyDeeplink = (deeplinkUrl: string) => {
    navigator.clipboard.writeText(deeplinkUrl);
    setCopiedLink(deeplinkUrl);
    setTimeout(() => setCopiedLink(null), 2500);
  };

  const handleDirectLaunch = (deeplinkUrl: string) => {
    try {
      window.location.href = deeplinkUrl;
    } catch {
      // Ignored on desktop browser
    }
  };

  return (
    <>
      <article
        className={`group relative rounded-2xl border transition-all duration-300 p-5 sm:p-6 backdrop-blur-xl shadow-lg ${
          isCompleted
            ? 'border-emerald-500/30 bg-slate-900/40 opacity-85'
            : `border-slate-800/90 bg-slate-900/70 ${categoryConfig.glowBorder} hover:bg-slate-900/90 hover:shadow-cyan-950/10`
        }`}
      >
        <div className="flex items-start gap-3.5 sm:gap-4">
          {/* Completion Checkbox & Step Number */}
          <div className="flex flex-col items-center gap-1.5 flex-shrink-0">
            <button
              type="button"
              onClick={onToggleComplete}
              className={`flex h-11 w-11 items-center justify-center rounded-xl border font-mono text-sm font-bold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-cyan-400 ${
                isCompleted
                  ? 'border-emerald-500 bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/30'
                  : 'border-slate-700/80 bg-slate-800/80 text-cyan-400 hover:border-cyan-500/50 hover:bg-slate-800'
              }`}
              title={isCompleted ? 'Mark step as incomplete' : 'Mark step as completed'}
              aria-label={`Step ${stepNumber}: ${action.actionName} - ${isCompleted ? 'Completed' : 'Incomplete'}`}
            >
              {isCompleted ? <CheckCircleIcon size={20} /> : stepNumber}
            </button>
            <span className="text-[10px] text-slate-500 font-medium">
              {isCompleted ? 'Done' : 'Step'}
            </span>
          </div>

          {/* Action Content */}
          <div className="flex-1 min-w-0">
            {/* Title & Category Badge */}
            <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
              <h3
                className={`text-base sm:text-lg font-bold tracking-tight transition-colors ${
                  isCompleted ? 'text-slate-400 line-through' : 'text-white'
                }`}
              >
                {action.actionName}
              </h3>

              <div className="flex items-center gap-2">
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold shadow-sm ${categoryConfig.badgeClass}`}
                >
                  {categoryConfig.icon}
                  {categoryConfig.label}
                </span>
              </div>
            </div>

            {/* Description */}
            {action.description && (
              <p className="text-xs sm:text-sm text-slate-300 mb-3.5 leading-relaxed">
                {action.description}
              </p>
            )}

            {/* Step Groups */}
            <div className="space-y-3">
              {action.stepGroups.map((group, gIdx) => (
                <div key={gIdx} className="space-y-2">
                  {group.steps && group.steps.length > 0 && (
                    <ul className="space-y-2 text-xs sm:text-sm text-slate-300">
                      {group.steps.map((stepText, sIdx) => (
                        <li key={sIdx} className="flex items-start gap-2.5">
                          <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-cyan-400 ring-2 ring-cyan-400/20" />
                          <span className="leading-relaxed">{stepText}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>

            {/* Validation Deeplink Pill */}
            {primaryValidation && (
              <div className="mt-3.5 inline-flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-slate-950/70 px-3 py-1.5 text-[11px] text-slate-300">
                <ShieldCheckIcon size={13} className="text-emerald-400" />
                <span className="text-slate-400">Target Check:</span>
                <span className="font-mono text-cyan-300 font-semibold">{primaryValidation.key}</span>
                {primaryValidation.value && (
                  <span className="font-mono text-slate-400">
                    ({primaryValidation.condition || '=='} {primaryValidation.value})
                  </span>
                )}
              </div>
            )}

            {/* Deeplink Interactive Bar */}
            {primaryDeeplink && primaryDeeplink.deeplink && (
              <div className="mt-4 pt-3.5 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  {/* Simulate One UI Button */}
                  <button
                    type="button"
                    onClick={() => setShowSimulator(true)}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md shadow-cyan-500/20 hover:from-cyan-400 hover:to-blue-500 transition-all active:scale-95"
                  >
                    <SettingsIcon size={14} />
                    <span>
                      {primaryDeeplink.message
                        ? `Open: ${primaryDeeplink.message}`
                        : 'Open in One UI Settings'}
                    </span>
                  </button>

                  {/* Direct Launch on Android */}
                  <button
                    type="button"
                    onClick={() => handleDirectLaunch(primaryDeeplink.deeplink)}
                    title="Directly trigger intent URI"
                    className="inline-flex items-center gap-1 rounded-xl border border-slate-700 bg-slate-800/80 px-2.5 py-1.5 text-xs text-slate-300 hover:text-white hover:bg-slate-700 transition-colors"
                  >
                    <ExternalLinkIcon size={13} />
                    <span>Launch</span>
                  </button>
                </div>

                {/* Copy Deeplink Button */}
                <button
                  type="button"
                  onClick={() => handleCopyDeeplink(primaryDeeplink.deeplink)}
                  title="Copy intent protocol URI"
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-950 px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                >
                  {copiedLink === primaryDeeplink.deeplink ? (
                    <>
                      <CheckCircleIcon size={13} className="text-emerald-400" />
                      <span className="text-emerald-400 font-medium text-[11px]">Copied Protocol</span>
                    </>
                  ) : (
                    <>
                      <CopyIcon size={13} />
                      <span className="font-mono text-[11px]">Copy URI</span>
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      </article>

      {/* Simulator Modal */}
      {showSimulator && primaryDeeplink && (
        <DeeplinkModal
          deeplink={primaryDeeplink}
          validationDeeplink={primaryValidation}
          actionTitle={action.actionName}
          onClose={() => setShowSimulator(false)}
        />
      )}
    </>
  );
};
