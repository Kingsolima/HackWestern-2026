import { useEffect, useState } from 'react'
import { askLiveToken, forgetLiveToken, storedLiveToken } from '../liveToken'
import {
  applyDrafts,
  needsLiveAgents,
  stillMissing,
  withDefaults,
  type Onboarded,
} from '../onboarding/answers'
import {
  ApiError,
  intake,
  type CadMeasure,
  type CompanyFact,
  type IntakeResult,
  type KnownArm,
  type SpecRow,
} from '../onboarding/intake'
import { EMPTY_ANSWERS, QUESTIONS, listOf, type OpenAnswers } from '../onboarding/questions'
import type { BomRow, Robot } from '../types'
import { SpecsReview } from './SpecsReview'

interface Props {
  demo: Robot
  /** The recorded example answers (data/onboarding_example.json); null while loading. */
  example: OpenAnswers | null
  /** From the welcome screen. */
  bom: BomRow[]
  cad: CadMeasure | null
  /** Set when the user comes back to edit: opens on the review screen. */
  initial: Onboarded | null
  onDone: (onboarded: Onboarded) => void
  /** Back to the welcome screen for another BOM. */
  onChangeBom: () => void
  /** The current step and the facts read so far, for the timeline and the brief. */
  onProgress: (step: number, company: CompanyFact[]) => void
}

const REVIEW = STEPS.indexOf('review')
const FILES = STEPS.indexOf('files')
const TOKEN_MESSAGE = 'Reading new answers makes a real Gemini call. Enter the live token:'

/** One open question at a time in the console, then every number the job will use for the user
 * to confirm. */
export function Onboarding({ demo, example, bom, cad, initial, onDone, onChangeBom, onProgress }: Props) {
  const [answers, setAnswers] = useState<OpenAnswers>(initial?.answers ?? EMPTY_ANSWERS)
  // What the files alone gave us (decides what the drivetrain question asks for).
  const [fromFiles, setFromFiles] = useState<SpecRow[] | null>(null)
  // The full reading, the inputs it was made from, and the user's edits on top of it.
  const [specs, setSpecs] = useState<SpecRow[]>(initial?.specs ?? [])
  const [company, setCompany] = useState<CompanyFact[]>(initial?.company ?? [])
  const [dropped, setDropped] = useState<string[]>([])
  // A parts list we recognise as a researched arm: no drivetrain question, no wheel numbers.
  const [arm, setArm] = useState<KnownArm | null>(initial?.arm ?? null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const inputsKey = (a: OpenAnswers) => JSON.stringify([a, bom, cad])
  const [readKey, setReadKey] = useState(initial ? inputsKey(initial.answers) : '')

  const [index, setIndex] = useState(initial ? REVIEW : 0)
  const [back, setBack] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const step = STEPS[index]
  const question = QUESTIONS.find((q) => q.id === step)
  const go = (to: number) => {
    setBack(to < index)
    setIndex(to)
    setError(null)
  }

  useEffect(() => {
    intake({ bom, cad, answers: null }).then((r) => setFromFiles(r.specs), console.error)
  }, [bom, cad])

  useEffect(() => onProgress(index, company), [index, company, onProgress])

  /** One Gemini reading of the answers. Asks for the live token only when the backend wants it. */
  const read = async (): Promise<IntakeResult | null> => {
    const input = { bom, cad, answers }
    try {
      return await intake(input, storedLiveToken())
    } catch (e) {
      if (!(e instanceof ApiError) || e.status !== 403) throw e
    }
    forgetLiveToken()
    const token = await askLiveToken(TOKEN_MESSAGE)
    if (!token) return null
    try {
      return await intake(input, token)
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) forgetLiveToken()
      throw e
    }
  }

  const work = async (label: string, job: () => Promise<void>) => {
    setBusy(label)
    setError(null)
    try {
      await job()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  const finish = () => {
    const applied = applyDrafts(specs, drafts)
    if (!applied.ok) return setError(applied.error)
    const cleaned = company.map((c) => ({ ...c, value: c.value.trim() })).filter((c) => c.value)
    const country = cleaned.find((c) => c.field === 'final_assembly_country')
    if (!country || !/^[A-Za-z]{2}$/.test(country.value)) {
      return setError('Final assembly needs a 2-letter country code, like US or CA.')
    }
    onDone({ answers, bom, company: cleaned, specs: applied.specs, arm })
  }

  /** Read the open answers (once per set of inputs) and open the review screen. */
  const readAnswers = async () => {
    if (readKey === inputsKey(answers, bom, cad)) return go(REVIEW) // nothing changed: keep edits
    const result = await read()
    if (!result) return setError('Reading new answers needs the live token.')
    setSpecs(result.specs)
    setCompany(withDefaults(result.company, demo))
    setDropped(result.dropped)
    setDrafts({})
    setReadKey(inputsKey(answers, bom, cad))
    go(REVIEW)
  }

  /** Check the current step and move on. */
  const next = () => {
    if (busy) return
    if (step === 'review') return finish()
    if (step === 'files') {
      if (bom.length === 0) return setError('Upload a BOM CSV, or use the sample BOM.')
      return void work('Reading your files…', async () => {
        const fromBom = await intake({ bom, cad, answers: null })
        setFromFiles(fromBom.specs)
        setArm(fromBom.known_arm ?? null)
        if (fromBom.known_arm) await readAnswers() // an arm has no drivetrain to ask about
        else go(index + 1)
      })
    }
    if (step === 'drivetrain') return void work('Reading your answers…', readAnswers)
    if (question?.required && !answers[question.id].trim()) return setError('Please type an answer.')
    go(index + 1)
  }

  // Enter goes on (Shift+Enter is a new line in an answer). Re-bound every render so the handler
  // always sees the current step.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Enter' || e.shiftKey) return
      const el = e.target as HTMLElement
      const text = el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && (el as HTMLInputElement).type !== 'file')
      if (!text && ['BUTTON', 'A', 'SUMMARY', 'INPUT'].includes(el.tagName)) return
      e.preventDefault()
      next()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const missing = fromFiles ? stillMissing(fromFiles) : []
  const found = (fromFiles ?? []).filter((s) => s.source === 'bom' || s.source === 'cad')
  const applied = applyDrafts(specs, drafts)
  const live = needsLiveAgents(applied.ok ? applied.specs : specs)

  return (
    <div className={`q${back ? ' back' : ''}`} key={index}>
      <div className="label">{step === 'review' ? 'Review' : `Question ${index + 1} of ${REVIEW}`}</div>

      {question && (
        <>
          <h1>{question.prompt}</h1>
          <p className="help">
            {step === 'drivetrain' && missing.length > 0
              ? `We still need ${listOf(missing)}. Anything you leave out keeps a default you can change on the next screen.`
              : question.help}
          </p>
          {step === 'drivetrain' && found.length > 0 && (
            <p className="help">
              From your files:{' '}
              {listOf(
                found.map(
                  (s) =>
                    `${s.label.toLowerCase()} ${s.value}${s.unit ? ` ${s.unit}` : ''}` +
                    (s.evidence?.startsWith('estimate') ? ' (an estimate)' : ''),
                ),
              )}
              .
            </p>
          )}
          <textarea
            className="answer"
            autoFocus
            rows={3}
            value={answers[question.id]}
            placeholder="Type your answer here…"
            aria-label={question.prompt}
            aria-invalid={error != null}
            onChange={(e) => {
              setAnswers({ ...answers, [question.id]: e.target.value })
              setError(null)
            }}
          />
        </>
      )}

      {step === 'review' && (
        <>
          <h1>Does this look right?</h1>
          <p className="help">These are the numbers the job will use. Change any of them.</p>
          <SpecsReview
            rows={specs}
            drafts={drafts}
            onDraft={(field, text) => {
              setDrafts({ ...drafts, [field]: text })
              setError(null)
            }}
          />
          <table className="specs">
            <caption>About you</caption>
            <tbody>
              {company.map((c) => {
                const acc = c.quote ? 'hi' : 'lo'
                return (
                  <tr key={c.field}>
                    <th scope="row">
                      <label htmlFor={`fact-${c.field}`}>{c.label}</label>
                      {c.quote && <span className="ev">“{c.quote}”</span>}
                    </th>
                    <td>
                      <input
                        id={`fact-${c.field}`}
                        className="wide"
                        value={c.value}
                        onChange={(e) => {
                          setCompany(company.map((x) => (x.field === c.field ? { ...x, value: e.target.value } : x)))
                          setError(null)
                        }}
                      />
                    </td>
                    <td>
                      <span className="src">
                        <span className={`dot ${acc}`} />
                        {c.quote ? 'Your words' : 'Default'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {dropped.length > 0 && (
            <details className="dropped">
              <summary>{dropped.length} things we read but could not confirm</summary>
              <ul>
                {dropped.map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
            </details>
          )}
          {live && (
            <p className="notice">
              Your drivetrain differs from the recorded demo, so agents will run live (up to 8 TinyFish agent runs,
              needs the live token).
            </p>
          )}
        </>
      )}

      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}

      <div className="nav">
        {busy ? (
          <span className="busy">{busy}</span>
        ) : (
          <>
            <h1 className="ob-prompt">Does this look right?</h1>
            {arm ? (
              <>
                <p className="ob-help muted">
                  Your parts list matches the {arm.robot}, so we did not ask about a drivetrain. Check what we read
                  about you below.
                </p>
                <div className="ob-specs">
                  <table>
                    <caption>{arm.arm.joint} joint: what a replacement motor is checked against</caption>
                    <tbody>
                      {[
                        ['Payload', `${arm.arm.payload_kg} kg`],
                        ['Reach', `${Math.round(arm.arm.reach_m * 1000)} mm`],
                        ['Gear ratio', `${arm.arm.gear_ratio} : 1`],
                        ['Bus voltage', `${arm.arm.bus_voltage_v} V`],
                        ['Safety factor', String(arm.arm.safety_factor)],
                      ].map(([label, value]) => (
                        <tr key={label}>
                          <th scope="row">{label}</th>
                          <td className="ob-spec-value">{value}</td>
                          <td>
                            <span className="badge source-default">from our research</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="ob-help muted">
                  These come from our research on the {arm.robot}, not from your parts list.
                </p>
              </>
            ) : (
              <>
                <p className="ob-help muted">
                  These are the numbers the job will use. Change any of them; each one shows where it came from.
                </p>
                <SpecsReview
                  rows={specs}
                  drafts={drafts}
                  onDraft={(field, text) => {
                    setDrafts({ ...drafts, [field]: text })
                    setError(null)
                  }}
                />
              </>
            )}
            <div className="ob-specs">
              <table>
                <caption>About you</caption>
                <tbody>
                  {company.map((c) => (
                    <tr key={c.field}>
                      <th scope="row">
                        <label htmlFor={`fact-${c.field}`}>{c.label}</label>
                        {c.quote && <span className="muted ob-evidence">“{c.quote}”</span>}
                      </th>
                      <td className="ob-spec-value">
                        <input
                          id={`fact-${c.field}`}
                          className="ob-input wide"
                          value={c.value}
                          onChange={(e) => {
                            setCompany(company.map((x) => (x.field === c.field ? { ...x, value: e.target.value } : x)))
                            setError(null)
                          }}
                        />
                      </td>
                      <td>
                        <span className={`badge source-${c.quote ? 'answer' : 'default'}`}>
                          {c.quote ? 'from your answer' : 'default'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {dropped.length > 0 && (
              <details className="ob-advanced">
                <summary>{dropped.length} things we read but could not confirm</summary>
                <ul>
                  {dropped.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              </details>
            )}
            {live && !arm && (
              <p className="ob-live">
                Your drivetrain differs from the recorded demo, so agents will run live (up to 8 TinyFish agent
                runs, needs the live token).
              </p>
            )}
          </>
        )}

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <div className="ob-nav">
          <button type="button" className="primary" onClick={next} disabled={busy != null}>
            {busy ?? (step === 'review' ? 'Find and Redesign' : 'OK')}
          </button>
          {!busy && (
            <span className="muted ob-hint">
              press <kbd>Enter</kbd>
            </span>
          )}
          {index > 0 && (
            <button type="button" className="secondary" onClick={() => go(step === 'review' && arm ? FILES : index - 1)} disabled={busy != null}>
              Back
            </button>
          )}
          {index === 0 && (
            <>
              {example && (
                <button type="button" className="ob-link" onClick={fillExample}>
                  Use the example
                </button>
              )}
              <button type="button" className="ob-link" onClick={onSkip}>
                Skip to the demo robot
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
