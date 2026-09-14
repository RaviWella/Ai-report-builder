/**

 * Chat composer: follow-up modes, scenario targets, quick actions, and message input.

 */

import React from 'react'

import { ArrowRight } from 'lucide-react'

import type { LatestTurnContext } from '../lib/latestTurnContext'

import { formatEditingPillLabel } from '../lib/latestTurnContext'

import DatamartQuickActions from './DatamartQuickActions'

import DatamartFollowUpModeToggle from './DatamartFollowUpModeToggle'

import DatamartModifyScenarioPicker from './DatamartModifyScenarioPicker'

import { followUpPlaceholder, type DatamartFollowUpMode } from '../lib/followUpMode'
import { clarificationComposerPlaceholder } from '../lib/clarificationReply'

import { canSendWithModifyTargets } from '../lib/modifyScenarioTargets'

import { dmColors, dmRadius } from '../lib/tokens'



export interface DatamartComposerProps {

  input: string

  composerHint: string | null

  /** Context for the blue “editing” pill (may be hidden while toolbar stays visible). */

  editingContext: LatestTurnContext | null

  /** Latest turn context for mode toggle / scenario chips (independent of pill dismiss). */

  toolbarContext?: LatestTurnContext | null

  showFollowUpMode: boolean

  awaitingClarification?: boolean

  clarificationAnchor?: string | null

  followUpMode: DatamartFollowUpMode

  onFollowUpModeChange: (mode: DatamartFollowUpMode) => void

  showQuickActions?: boolean

  loading: boolean

  loadingHistory: boolean

  inputRef: React.Ref<HTMLTextAreaElement | null>

  onInputChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void

  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void

  onSubmit: () => void

  onDismissHint: () => void

  onDismissEditingContext: () => void

  modifyTargetIds?: string[]

  onModifyTargetIdsChange?: (ids: string[]) => void

  onSendFollowUp?: (prompt: string) => void

  onAddChart?: () => void

}



const DatamartComposer: React.FC<DatamartComposerProps> = ({

  input,

  composerHint,

  editingContext,

  toolbarContext: toolbarContextProp,

  showFollowUpMode,

  awaitingClarification = false,

  clarificationAnchor = null,

  followUpMode,

  onFollowUpModeChange,

  showQuickActions = false,

  loading,

  loadingHistory,

  inputRef,

  onInputChange,

  onKeyDown,

  onSubmit,

  onDismissHint,

  onDismissEditingContext,

  modifyTargetIds = [],

  onModifyTargetIdsChange,

  onSendFollowUp,

  onAddChart,

}) => {

  const disabled = loading || loadingHistory

  const toolbarContext = toolbarContextProp ?? editingContext

  const showScenarioPicker =

    showFollowUpMode &&

    followUpMode === 'continue_last' &&

    !!toolbarContext?.multiScenario &&

    toolbarContext.scenarios.length > 1 &&

    !!onModifyTargetIdsChange

  const targetsOk = canSendWithModifyTargets(

    !!toolbarContext?.multiScenario,

    followUpMode,

    modifyTargetIds,

  )

  const canSend = !!input.trim() && !disabled && targetsOk

  const showQuickActionRow =

    showQuickActions && !!toolbarContext && !!onSendFollowUp

  const showToolbar =

    !!toolbarContext &&

    (showFollowUpMode || showQuickActionRow)



  return (

    <div className="datamart-composer-root" style={{ overflow: 'visible', zIndex: 5 }}>

      <div style={{ maxWidth: 960, margin: '0 auto', width: '100%', minWidth: 0 }}>

        {composerHint && (

          <div

            style={{

              display: 'flex',

              alignItems: 'center',

              justifyContent: 'space-between',

              gap: 8,

              marginBottom: 8,

              padding: '8px 12px',

              borderRadius: dmRadius.md,

              background: dmColors.purpleBg,

              border: `1px solid ${dmColors.purpleBorder}`,

              fontSize: 12,

              color: '#5b21b6',

            }}

          >

            <span style={{ lineHeight: 1.45 }}>{composerHint}</span>

            <button

              type="button"

              onClick={onDismissHint}

              style={{

                background: 'none',

                border: 'none',

                cursor: 'pointer',

                fontSize: 16,

                lineHeight: 1,

                color: dmColors.purple,

                padding: 0,

                flexShrink: 0,

              }}

              aria-label="Dismiss"

            >

              ×

            </button>

          </div>

        )}



        {!composerHint && !showFollowUpMode && editingContext?.sql && (

          <div

            style={{

              display: 'flex',

              alignItems: 'center',

              justifyContent: 'space-between',

              gap: 8,

              marginBottom: 8,

              padding: '8px 12px',

              borderRadius: dmRadius.md,

              background: dmColors.brandMuted,

              border: `1px solid ${dmColors.brandBorder}`,

              fontSize: 12,

              color: dmColors.brand,

            }}

          >

            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>

              {formatEditingPillLabel(editingContext.question)}

            </span>

            <button

              type="button"

              onClick={onDismissEditingContext}

              style={{

                background: 'none',

                border: 'none',

                cursor: 'pointer',

                fontSize: 12,

                fontWeight: 600,

                color: dmColors.brand,

                padding: 0,

                flexShrink: 0,

              }}

            >

              Clear

            </button>

          </div>

        )}



        <form

          className="dm-composer-form"

          onSubmit={(e) => {

            e.preventDefault()

            onSubmit()

          }}

        >

          {showToolbar && (

            <div

              onMouseDown={(e) => e.stopPropagation()}

              style={{

                display: 'flex',

                flexDirection: 'column',

                gap: showQuickActionRow ? 10 : 8,

                padding: '10px 12px',

                borderBottom: `1px solid ${dmColors.borderLight}`,

                background: dmColors.surfaceMuted,

              }}

            >

              {showFollowUpMode && (

                <DatamartFollowUpModeToggle

                  mode={followUpMode}

                  lastQuestionLabel={toolbarContext!.question}

                  disabled={disabled}

                  embedded

                  onChange={onFollowUpModeChange}

                />

              )}

              {showScenarioPicker && (

                <DatamartModifyScenarioPicker

                  scenarios={toolbarContext!.scenarios}

                  selectedIds={modifyTargetIds}

                  disabled={disabled}

                  onChange={onModifyTargetIdsChange!}

                />

              )}

              {showQuickActionRow && (

                <DatamartQuickActions

                  context={toolbarContext!}

                  disabled={loading}

                  compact

                  onSendFollowUp={onSendFollowUp!}

                  onAddChart={onAddChart}

                />

              )}

            </div>

          )}



          <div

            style={{

              display: 'flex',

              alignItems: 'center',

              gap: 10,

              padding: '12px 14px',

              minHeight: 52,

              boxSizing: 'border-box',

            }}

          >

            <label htmlFor="datamart-composer-input" className="dm-sr-only">
              Ask a question about your data
            </label>

            <textarea

              id="datamart-composer-input"

              ref={inputRef as React.RefObject<HTMLTextAreaElement>}

              data-testid="datamart-composer-input"

              value={input}

              onChange={onInputChange}

              onKeyDown={onKeyDown}

              placeholder={

                awaitingClarification

                  ? clarificationComposerPlaceholder(clarificationAnchor)

                  : showFollowUpMode

                    ? followUpPlaceholder(followUpMode)

                    : 'Ask about employees, payroll, attendance, leave...'

              }

              disabled={disabled}

              rows={1}

              style={{

                flex: 1,

                fontSize: 15,

                border: 'none',

                outline: 'none',

                resize: 'none',

                lineHeight: 1.5,

                color: dmColors.text,

                background: 'transparent',

                maxHeight: 120,

                fontFamily: 'inherit',

                padding: '2px 0',

                margin: 0,

                minWidth: 0,

                minHeight: 24,

              }}

            />

            <button

              type="submit"

              data-testid="datamart-composer-send"

              disabled={!canSend}

              className={`dm-composer-send ${canSend ? 'dm-composer-send--on' : 'dm-composer-send--off'}`}

              aria-label="Send message"

            >

              <ArrowRight size={17} strokeWidth={2.25} />

            </button>

          </div>

        </form>



        <p className="dm-composer-hint">
          Enter to send · Shift+Enter new line
          {showFollowUpMode ? ' · Alt+1 Modify · Alt+2 Scenario · Alt+3 Free' : ''}
        </p>

      </div>

    </div>

  )

}



export default DatamartComposer


