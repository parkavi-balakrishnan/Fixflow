import React, { useState } from 'react';
import { DeviceSelector } from './DeviceSelector';
import { SparklesIcon, ArrowRightIcon, ZapIcon, AlertTriangleIcon, SearchIcon } from './Icons';

interface TroubleshootingFormProps {
  onSubmit: (params: { query: string; device?: string; model?: string }) => void;
  isLoading: boolean;
}

interface BenchmarkQuery {
  title: string;
  category: string;
  query: string;
  device: string;
  model: string;
  highlight: string;
}

const BENCHMARK_EXAMPLES: BenchmarkQuery[] = [
  {
    title: 'Screen Flickering & Damage',
    category: 'Display',
    query: 'The mobile phone screen is cracked and flashes intermittently.',
    device: 'Galaxy S24',
    model: 'SM-S921B',
    highlight: 'Triggers FastPath Cache + Screen Repair Deeplinks',
  },
  {
    title: 'Rapid Battery Drain',
    category: 'Battery',
    query: 'My phone battery is draining very quickly even in standby mode.',
    device: 'Galaxy S24 Ultra',
    model: 'SM-S928B',
    highlight: 'Optimizes Power & Background usage settings',
  },
  {
    title: 'Wi-Fi Reconnection Loop',
    category: 'Connectivity',
    query: 'Wi-Fi connection keeps dropping frequently and will not reconnect.',
    device: 'Galaxy Tab S9',
    model: 'SM-X710',
    highlight: 'Network reset & band steering settings',
  },
  {
    title: 'Display Vertical Lines',
    category: 'Hardware',
    query: 'My Galaxy Tab screen shows purple vertical lines across the display.',
    device: 'Galaxy Tab S9',
    model: 'SM-X710',
    highlight: 'Samsung Care+ authorized service dispatch',
  },
];

const QUICK_CATEGORIES = [
  { label: 'All Issues', icon: '✨' },
  { label: 'Screen & Display', icon: '📱' },
  { label: 'Battery & Power', icon: '🔋' },
  { label: 'Wi-Fi & Bluetooth', icon: '📶' },
  { label: 'System & Apps', icon: '⚙️' },
];

export const TroubleshootingForm: React.FC<TroubleshootingFormProps> = ({
  onSubmit,
  isLoading,
}) => {
  const [query, setQuery] = useState('');
  const [device, setDevice] = useState('');
  const [model, setModel] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState('All Issues');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanQuery = query.trim();

    if (!cleanQuery) {
      setValidationError('Please describe the problem you are experiencing with your Galaxy device.');
      return;
    }

    if (cleanQuery.length > 2000) {
      setValidationError('Query exceeds maximum limit of 2000 characters.');
      return;
    }

    setValidationError(null);
    onSubmit({
      query: cleanQuery,
      device: device.trim() || undefined,
      model: model.trim() || undefined,
    });
  };

  const handleApplyExample = (ex: BenchmarkQuery) => {
    if (isLoading) return;
    setQuery(ex.query);
    setDevice(ex.device);
    setModel(ex.model);
    setValidationError(null);
  };

  return (
    <div className="w-full max-w-3xl mx-auto space-y-8 animate-in fade-in duration-300">
      {/* Hero Header */}
      <div className="text-center pt-2 sm:pt-4">
        {/* Top Feature Pill */}
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-950/40 px-3.5 py-1.5 text-xs font-semibold text-cyan-300 backdrop-blur-md mb-5 shadow-lg shadow-cyan-950/30">
          <span className="flex h-2 w-2 rounded-full bg-cyan-400 animate-pulse"></span>
          <span>Samsung PRISM 2026 • AI Guided Troubleshooting Engine</span>
        </div>

        {/* Main Title */}
        <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white font-sans leading-tight">
          Resolve Galaxy Issues with{' '}
          <span className="galaxy-text-gradient">Precision AI</span>
        </h1>

        <p className="mt-3.5 text-sm sm:text-base text-slate-400 max-w-xl mx-auto leading-relaxed">
          Describe any symptom with your Samsung phone, fold, or tablet. FixFlow generates ordered, validated remediation steps and direct One UI Settings deeplinks.
        </p>

        {/* Quick Category Chips */}
        <div className="flex flex-wrap items-center justify-center gap-2 mt-6">
          {QUICK_CATEGORIES.map((cat) => (
            <button
              key={cat.label}
              type="button"
              onClick={() => setSelectedCategory(cat.label)}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-all ${
                selectedCategory === cat.label
                  ? 'border border-cyan-500/60 bg-cyan-500/20 text-cyan-300 shadow-sm shadow-cyan-500/20'
                  : 'border border-slate-800 bg-slate-900/50 text-slate-400 hover:border-slate-700 hover:text-slate-200'
              }`}
            >
              <span>{cat.icon}</span>
              <span>{cat.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Main Troubleshooting Form Card */}
      <div className="relative rounded-3xl border border-slate-800/90 bg-slate-900/70 p-6 sm:p-8 shadow-2xl backdrop-blur-2xl">
        {/* Glow ambient background accent */}
        <div className="absolute -top-12 -left-12 h-40 w-40 rounded-full bg-cyan-500/10 blur-3xl pointer-events-none"></div>

        <form onSubmit={handleSubmit} className="space-y-6 relative z-10" noValidate>
          {/* Query Input Section */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label
                htmlFor="query-input"
                className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-200"
              >
                <SearchIcon size={14} className="text-cyan-400" />
                <span>Describe Device Problem</span>
                <span className="text-cyan-400">*</span>
              </label>

              <span className="text-[11px] text-slate-500 font-mono">
                {query.length} / 2000
              </span>
            </div>

            <div className="relative">
              <textarea
                id="query-input"
                rows={3}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  if (validationError) setValidationError(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                    handleSubmit(e);
                  }
                }}
                disabled={isLoading}
                placeholder="e.g. My Galaxy screen is flickering when opening apps, or battery drops fast in standby..."
                className={`w-full resize-none rounded-2xl border bg-slate-950/90 px-4 py-3.5 text-sm sm:text-base text-slate-100 placeholder-slate-500 shadow-inner transition-colors focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50 ${
                  validationError
                    ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/20'
                    : 'border-slate-700/80 focus:border-cyan-500 focus:ring-cyan-500/20'
                }`}
                aria-invalid={!!validationError}
                aria-describedby={validationError ? 'query-error' : undefined}
                required
              />

              {query && !isLoading && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="absolute right-3 bottom-3 text-slate-500 hover:text-slate-200 text-xs p-1 rounded-md"
                  aria-label="Clear query text"
                >
                  ✕ Clear
                </button>
              )}
            </div>

            {validationError && (
              <p id="query-error" className="mt-2 text-xs text-rose-400 flex items-center gap-1.5 font-medium animate-in fade-in">
                <AlertTriangleIcon size={14} />
                <span>{validationError}</span>
              </p>
            )}
          </div>

          {/* Device & Model Information Component */}
          <div className="pt-2 border-t border-slate-800/80">
            <DeviceSelector
              device={device}
              model={model}
              onDeviceChange={setDevice}
              onModelChange={setModel}
              disabled={isLoading}
            />
          </div>

          {/* Submit Action */}
          <div className="pt-3">
            <button
              type="submit"
              disabled={isLoading || !query.trim()}
              className="group relative flex w-full items-center justify-center gap-2.5 rounded-2xl bg-gradient-to-r from-cyan-500 via-sky-500 to-blue-600 px-6 py-4 text-base font-bold text-white shadow-xl shadow-cyan-500/25 transition-all duration-200 hover:from-cyan-400 hover:to-blue-500 hover:shadow-cyan-500/40 focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:ring-offset-2 focus:ring-offset-slate-950 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
            >
              {isLoading ? (
                <>
                  <svg
                    className="h-5 w-5 animate-spin text-white"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  <span>Synthesizing Remediation Plan...</span>
                </>
              ) : (
                <>
                  <SparklesIcon size={18} />
                  <span>Troubleshoot Problem</span>
                  <ArrowRightIcon size={18} className="transition-transform group-hover:translate-x-1" />
                </>
              )}
            </button>

            <div className="mt-3 flex items-center justify-center gap-4 text-[11px] text-slate-500">
              <span>
                Shortcut: <kbd className="rounded border border-slate-700 bg-slate-800 px-1 py-0.5 text-[10px] text-slate-300 font-mono">⌘</kbd> + <kbd className="rounded border border-slate-700 bg-slate-800 px-1 py-0.5 text-[10px] text-slate-300 font-mono">Enter</kbd>
              </span>
              <span>•</span>
              <span className="flex items-center gap-1 text-slate-400">
                <ZapIcon size={12} className="text-cyan-400" />
                FastPath Semantic Cache Enabled
              </span>
            </div>
          </div>
        </form>
      </div>

      {/* Samsung PRISM Benchmark Scenarios for Demo */}
      <div className="space-y-3">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <ZapIcon size={14} className="text-cyan-400" />
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              PRISM Hackathon Benchmark Scenarios
            </span>
          </div>
          <span className="text-[11px] text-slate-500">
            Click to load verified test case
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {BENCHMARK_EXAMPLES.map((ex) => (
            <button
              key={ex.title}
              type="button"
              onClick={() => handleApplyExample(ex)}
              disabled={isLoading}
              className="group flex flex-col text-left rounded-2xl border border-slate-800/80 bg-slate-900/50 p-4 hover:border-cyan-500/40 hover:bg-slate-900/90 transition-all text-xs relative overflow-hidden"
            >
              <div className="flex items-center justify-between w-full mb-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="font-bold text-slate-200 group-hover:text-cyan-300 transition-colors">
                    {ex.title}
                  </span>
                  <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-mono text-cyan-400">
                    {ex.category}
                  </span>
                </div>
                <span className="text-[11px] text-slate-400 font-mono">
                  {ex.device}
                </span>
              </div>

              <p className="text-slate-400 line-clamp-2 group-hover:text-slate-300 transition-colors leading-relaxed mb-2">
                "{ex.query}"
              </p>

              <span className="text-[10px] text-cyan-400/90 font-medium">
                → {ex.highlight}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
