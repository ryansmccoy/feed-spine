/**
 * Resize Handle Component
 * 
 * Draggable handle for resizing panels in the newsfeed layout.
 */

import { clsx } from 'clsx'

export interface ResizeHandleProps {
  onMouseDown?: (e: React.MouseEvent) => void
  direction?: 'horizontal' | 'vertical'
  isResizing?: boolean
}

export function ResizeHandle({ 
  onMouseDown, 
  direction = 'horizontal',
  isResizing = false 
}: ResizeHandleProps) {
  return (
    <div
      onMouseDown={onMouseDown}
      className={clsx(
        'group flex items-center justify-center transition-colors',
        direction === 'horizontal'
          ? 'w-1 cursor-col-resize hover:bg-primary-500/20'
          : 'h-1 cursor-row-resize hover:bg-primary-500/20',
        isResizing && 'bg-primary-500/30',
        !onMouseDown && 'cursor-default'
      )}
    >
      <div
        className={clsx(
          'rounded-full bg-gray-300 dark:bg-gray-600 transition-colors',
          direction === 'horizontal' ? 'w-0.5 h-8' : 'h-0.5 w-8',
          'group-hover:bg-primary-500',
          isResizing && 'bg-primary-500'
        )}
      />
    </div>
  )
}
