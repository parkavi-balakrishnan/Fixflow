import React, { useState } from 'react';
import type { TroubleshootingResultData } from '../types/fixflow';
import { TroubleshootingStep } from './TroubleshootingStep';
import { TelemetryDrawer } from './TelemetryDrawer';
import {
  RotateCcwIcon,
  CopyIcon,
  CheckCircleIcon,
  SparklesIcon,
  PhoneIcon,
} from './Icons';

interface TroubleshootingResultProps {
  data: TroubleshootingResultData;
  onReset: () => void;
}

export const TroubleshootingResult: React.FC<TroubleshootingResultProps> = ({
  data,
  onReset,
}) => {
  const { response, telemetry, submittedQuery, submittedDevice, submittedModel } = data;

  // Flatten all actions from all contexts to ensure sequential ordering
  const allActions = response.contexts.flatMap((c) => c.actions);
  const primaryContext = response.contexts[0];

  // Track completed steps by index
  const [completedSteps, setCompletedSteps] = useState<Record<number, boolean>>({});
  const [copiedPlan, setCopiedPlan] = useState(false);
  const [resolvedFeedback, setResolvedFeedback] = useState<'yes' | 'no' | null>(null);

  const completedCount = Object.values(completedSteps).filter(Boolean).length;
  const totalCount = allActions.length;
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  const toggleStepComplete = (index: number) => {
    setCompletedSteps((prev) => ({
      ...prev,
      [index]: !prev[index],
    }));
  };

  const handleCopyFullPlan = () => {
    let planText = `FixFlow Guided Remediation Plan\n`;
    planText += `Issue: "${submittedQuery}"\n`;
    if (submittedDevice || submittedModel) {
      planText += `Device: ${[submittedDevice, submittedModel].filter(Boolean).join(' ')}\n`;
    }
    planText += `\nSteps:\n`;

    allActions.forEach((action, idx) => {
      planText += `${idx + 1}. ${action.actionName} (${action.category || 'guided'})\n`;
      if (action.description) planText += `   ${action.description}\n`;
      action.stepGroups.forEach((sg) => {
        sg.steps.forEach((step) => {
          planText += `   - ${step}\n`;
        });
        if (sg.actionableDeeplink?.deeplink) {
          planText += `   * Settings Intent: ${sg.actionableDeeplink.deeplink}\n`;
        }
      });
      planText += `\n`;
    });

    navigator.clipboard.writeText(planText);
    setCopiedPlan(true);
    setTimeout(() => setCopiedPlan(false), 2500);
  };

  return (
    <section className="w-full max-w-4xl mx-auto space-y-6 pb-12 animate-in fade-in duration-300">
      {/* Top AI Telemetry Drawer */}
      <TelemetryDrawer telemetry={telemetry} response={response} />

      {/* Primary Goal & Remediation Overview Card */}
      <div className="rounded-3xl border border-slate-800/90 bg-slate-900/70 p-6 sm:p-8 backdrop-blur-2xl shadow-2xl relative overflow-hidden">
        {/* Subtle background ambient blur */}
        <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-cyan-500/10 blur-3xl pointer-events-none"></div>

        <div className="relative z-10">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-950/40 px-3 py-1 text-xs font-semibold text-cyan-300">
              <SparklesIcon size={14} className="text-cyan-400" />
              <span>Smart Diagnostic Resolved</span>
            </div>

            <div className="flex items-center gap-2">
              {/* Copy Plan Button */}
              <button
                type="button"
                onClick={handleCopyFullPlan}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700/80 bg-slate-800/80 px-3 py-1.5 text-xs font-semibold text-slate-200 transition-all hover:bg-slate-700 hover:text-white"
                title="Copy entire troubleshooting plan to clipboard"
              >
                {copiedPlan ? (
                  <>
                    <CheckCircleIcon size={13} className="text-emerald-400" />
                    <span className="text-emerald-400">Plan Copied</span>
                  </>
                ) : (
                  <>
                    <CopyIcon size={13} />
                    <span>Copy Full Plan</span>
                  </>
                )}
              </button>

              {/* Start Over Button */}
              <button
                type="button"
                onClick={onReset}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800/80 px-3.5 py-1.5 text-xs font-semibold text-slate-200 transition-all hover:bg-slate-700 hover:text-white active:scale-95"
              >
                <RotateCcwIcon size={13} />
                <span>New Problem</span>
              </button>
            </div>
          </div>

          {/* Goal Title */}
          <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white font-sans">
            {primaryContext?.title || primaryContext?.goal || 'Recommended Troubleshooting Plan'}
          </h2>

          {primaryContext?.goal && primaryContext?.title && primaryContext.goal !== primaryContext.title && (
            <p className="mt-1 text-xs sm:text-sm text-cyan-400 font-medium">
              {primaryContext.goal}
            </p>
          )}

          {/* User Query & Device Metadata Grid */}
          <div className="mt-5 pt-4 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-3">
              <span className="text-slate-400 block mb-1 font-medium">Reported Symptom:</span>
              <span className="text-slate-200 font-semibold italic">"{submittedQuery}"</span>
            </div>

            <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-3">
              <div className="flex items-center gap-1.5 text-slate-400 mb-1 font-medium">
                <PhoneIcon size={13} />
                <span>Target Samsung Hardware:</span>
              </div>
              <span className="text-slate-200 font-semibold font-mono">
                {[submittedDevice, submittedModel].filter(Boolean).join(' • ') || 'Universal Samsung Galaxy'}
              </span>
            </div>
          </div>

          {/* Interactive Remediation Progress Bar */}
          <div className="mt-6 pt-5 border-t border-slate-800/80">
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="font-semibold text-slate-300">
                Remediation Progress: {completedCount} of {totalCount} completed
              </span>
              <span className="font-mono font-bold text-cyan-400">
                {progressPercent}%
              </span>
            </div>

            <div className="h-2.5 w-full rounded-full bg-slate-950 border border-slate-800 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 via-sky-400 to-emerald-400 transition-all duration-300 rounded-full"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Steps List Header */}
      <div className="flex items-center justify-between px-2">
        <div className="flex items-center gap-2.5">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Guided Step-by-Step Flow
          </span>
          <span className="rounded-full bg-cyan-950 border border-cyan-500/30 px-2.5 py-0.5 text-xs font-bold text-cyan-400">
            {allActions.length} Actions
          </span>
        </div>
        <span className="text-xs text-slate-400 hidden sm:inline">
          Ordered from quick-settings checks to authorized service
        </span>
      </div>

      {/* Ordered Steps List */}
      <div className="space-y-4">
        {allActions.map((action, idx) => (
          <TroubleshootingStep
            key={`${action.actionName}-${idx}`}
            action={action}
            index={idx}
            isCompleted={!!completedSteps[idx]}
            onToggleComplete={() => toggleStepComplete(idx)}
          />
        ))}
      </div>

      {/* Feedback & Problem Solved Banner */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 text-center backdrop-blur-xl">
        <h4 className="text-sm font-semibold text-white mb-2">
          Did this guided plan resolve your problem?
        </h4>
        <div className="flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => setResolvedFeedback('yes')}
            className={`inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-semibold transition-all ${
              resolvedFeedback === 'yes'
                ? 'bg-emerald-500 text-slate-950 font-bold'
                : 'border border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700'
            }`}
          >
            <CheckCircleIcon size={14} />
            <span>Yes, problem solved!</span>
          </button>
          <button
            type="button"
            onClick={() => setResolvedFeedback('no')}
            className={`inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-semibold transition-all ${
              resolvedFeedback === 'no'
                ? 'bg-rose-500 text-white font-bold'
                : 'border border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700'
            }`}
          >
            <span>Still having issues</span>
          </button>
        </div>

        {resolvedFeedback === 'yes' && (
          <p className="mt-3 text-xs text-emerald-400 font-medium animate-in fade-in">
            🎉 Great! FixFlow's FastPath AI engine successfully guided you through resolution.
          </p>
        )}

        {resolvedFeedback === 'no' && (
          <p className="mt-3 text-xs text-amber-300 font-medium animate-in fade-in">
            We recommend visiting an authorized Samsung Walk-in Service Center or scheduling a Samsung Care+ repair.
          </p>
        )}
      </div>

      {/* Bottom Start Over Action */}
      <div className="pt-4 text-center">
        <button
          type="button"
          onClick={onReset}
          className="inline-flex items-center gap-2 rounded-xl bg-slate-800/90 px-6 py-3 text-sm font-semibold text-white border border-slate-700 hover:bg-slate-700 hover:border-slate-600 transition-all shadow-md active:scale-95"
        >
          <RotateCcwIcon size={15} className="text-cyan-400" />
          <span>Troubleshoot Another Device Problem</span>
        </button>
      </div>
    </section>
  );
};
