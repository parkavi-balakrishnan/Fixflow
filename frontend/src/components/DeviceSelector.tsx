import React from 'react';
import { PhoneIcon, FoldableIcon, TabletIcon, WatchIcon, CpuIcon } from './Icons';

interface DeviceSelectorProps {
  device: string;
  model: string;
  onDeviceChange: (device: string) => void;
  onModelChange: (model: string) => void;
  disabled?: boolean;
}

interface PresetDevice {
  label: string;
  device: string;
  model: string;
  type: 'phone' | 'foldable' | 'tablet' | 'watch' | 'laptop';
}

const COMMON_DEVICES: PresetDevice[] = [
  { label: 'Galaxy S24 Ultra', device: 'Galaxy S24 Ultra', model: 'SM-S928B', type: 'phone' },
  { label: 'Galaxy Z Fold 6', device: 'Galaxy Z Fold6', model: 'SM-F956B', type: 'foldable' },
  { label: 'Galaxy Z Flip 6', device: 'Galaxy Z Flip6', model: 'SM-F741B', type: 'foldable' },
  { label: 'Galaxy Tab S9', device: 'Galaxy Tab S9', model: 'SM-X710', type: 'tablet' },
  { label: 'Galaxy Watch 6', device: 'Galaxy Watch6', model: 'SM-R930', type: 'watch' },
];

export const DeviceSelector: React.FC<DeviceSelectorProps> = ({
  device,
  model,
  onDeviceChange,
  onModelChange,
  disabled = false,
}) => {
  const handleQuickSelect = (preset: PresetDevice) => {
    if (disabled) return;
    if (device === preset.device && model === preset.model) {
      // Toggle off if already selected
      onDeviceChange('');
      onModelChange('');
    } else {
      onDeviceChange(preset.device);
      onModelChange(preset.model);
    }
  };

  const getDeviceIcon = (type: PresetDevice['type']) => {
    switch (type) {
      case 'foldable':
        return <FoldableIcon size={14} />;
      case 'tablet':
        return <TabletIcon size={14} />;
      case 'watch':
        return <WatchIcon size={14} />;
      case 'laptop':
        return <CpuIcon size={14} />;
      default:
        return <PhoneIcon size={14} />;
    }
  };

  return (
    <div className="space-y-4">
      {/* Quick Select Device Chips */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Quick-Select Samsung Device
          </span>
          <span className="text-[10px] text-slate-500">
            Form-factor tuned retrieval
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
          {COMMON_DEVICES.map((preset) => {
            const isSelected = device === preset.device && model === preset.model;
            return (
              <button
                key={preset.label}
                type="button"
                onClick={() => handleQuickSelect(preset)}
                disabled={disabled}
                className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium transition-all ${
                  isSelected
                    ? 'border border-cyan-500 bg-cyan-500/20 text-cyan-200 shadow-sm shadow-cyan-500/30'
                    : 'border border-slate-800 bg-slate-900/60 text-slate-400 hover:border-slate-700 hover:bg-slate-800/80 hover:text-slate-200'
                } disabled:pointer-events-none disabled:opacity-50`}
              >
                <span className={isSelected ? 'text-cyan-400' : 'text-slate-500'}>
                  {getDeviceIcon(preset.type)}
                </span>
                <span>{preset.label}</span>
                {isSelected && (
                  <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 ml-0.5 animate-pulse" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Manual Input Fields Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        {/* Device Field */}
        <div>
          <label
            htmlFor="device-input"
            className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5"
          >
            Device Series / Form Factor
          </label>
          <div className="relative">
            <input
              id="device-input"
              type="text"
              value={device}
              onChange={(e) => onDeviceChange(e.target.value)}
              disabled={disabled}
              placeholder="e.g. Galaxy S24, Tablet, Fold"
              className="w-full rounded-xl border border-slate-700/80 bg-slate-950/80 px-3.5 py-2.5 text-xs sm:text-sm text-slate-100 placeholder-slate-500 shadow-inner transition-colors focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50"
            />
            {device && !disabled && (
              <button
                type="button"
                onClick={() => onDeviceChange('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-200 text-xs p-1"
                aria-label="Clear device"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Model Field */}
        <div>
          <label
            htmlFor="model-input"
            className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5"
          >
            Model Code (Optional)
          </label>
          <div className="relative">
            <input
              id="model-input"
              type="text"
              value={model}
              onChange={(e) => onModelChange(e.target.value)}
              disabled={disabled}
              placeholder="e.g. SM-S928B, SM-X710"
              className="w-full rounded-xl border border-slate-700/80 bg-slate-950/80 px-3.5 py-2.5 text-xs sm:text-sm text-slate-100 placeholder-slate-500 shadow-inner transition-colors focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50 font-mono"
            />
            {model && !disabled && (
              <button
                type="button"
                onClick={() => onModelChange('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-200 text-xs p-1"
                aria-label="Clear model"
              >
                ✕
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
