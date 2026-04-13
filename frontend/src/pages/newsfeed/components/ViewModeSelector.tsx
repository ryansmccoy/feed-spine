/**
 * View Mode Selector Component
 * 
 * Dropdown menu for selecting article display mode.
 */

import { useState } from 'react'
import { 
  Check, 
  ChevronRight,
  Rows3,
  LayoutList,
  List,
  LayoutGrid,
  Table,
} from 'lucide-react'
import { clsx } from 'clsx'
import type { ViewMode } from '../types'
import { VIEW_MODES } from '../constants'

// Icon mapping
const ICONS = {
  Rows3,
  LayoutList,
  List,
  LayoutGrid,
  Table,
} as const

interface ViewModeSelectorProps {
  viewMode: ViewMode
  onChange: (mode: ViewMode) => void
}

export function ViewModeSelector({ viewMode, onChange }: ViewModeSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const current = VIEW_MODES.find(v => v.id === viewMode)!
  const CurrentIcon = ICONS[current.icon as keyof typeof ICONS]

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          'flex items-center gap-1.5 h-7 px-2 rounded border',
          'border-gray-200 dark:border-[#2D2D43]',
          'text-xs font-medium text-gray-600 dark:text-gray-400',
          'hover:bg-gray-50 dark:hover:bg-[#2D2D43]',
          'transition-colors'
        )}
        title="Change view mode"
      >
        <CurrentIcon className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">{current.label}</span>
        <ChevronRight 
          className={clsx(
            'h-3 w-3 transition-transform', 
            isOpen && 'rotate-90'
          )} 
        />
      </button>
      
      {isOpen && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-10" 
            onClick={() => setIsOpen(false)} 
          />
          
          {/* Dropdown */}
          <div className={clsx(
            'absolute right-0 top-full mt-1 z-20 w-48',
            'rounded-lg border border-gray-200 dark:border-[#2D2D43]',
            'bg-white dark:bg-[#1E1E2D] shadow-lg py-1'
          )}>
            {VIEW_MODES.map((mode) => {
              const Icon = ICONS[mode.icon as keyof typeof ICONS]
              const isSelected = viewMode === mode.id
              
              return (
                <button
                  key={mode.id}
                  onClick={() => {
                    onChange(mode.id)
                    setIsOpen(false)
                  }}
                  className={clsx(
                    'w-full flex items-center gap-2 px-3 py-2 text-left text-xs transition-colors',
                    isSelected
                      ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/20 dark:text-primary-400'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-[#2D2D43]'
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <div className="flex-1">
                    <div className="font-medium">{mode.label}</div>
                    <div className="text-[10px] text-gray-500 dark:text-gray-400">
                      {mode.description}
                    </div>
                  </div>
                  {isSelected && <Check className="h-3.5 w-3.5" />}
                </button>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
