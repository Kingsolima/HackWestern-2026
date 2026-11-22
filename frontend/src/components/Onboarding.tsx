import { useEffect, useState } from 'react'
import { askLiveToken, forgetLiveToken, storedLiveToken } from '../liveToken'
import { applyDrafts, needsLiveAgents, stillMissing, withDefaults, type Onboarded } from '../onboarding/answers'
import {
  ApiError,
  intake,
  type CadMeasure,
  type CompanyFact,
  type IntakeResult,
  type KnownArm,
  type SpecRow,
} from '../onboarding/intake'
import { EMPTY_ANSWERS, QUESTIONS, listOf, stepsFor, type OpenAnswers, type Step } from '../onboarding/questions'
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
  /** Where the user is, the facts read so far and the arm the parts list matched, for the
   * timeline, the brief and the 3D view. */
  onProgress: (progress: Progress) => void
}

export interface Progress {
  steps: readonly Step[]
  index: number
  company: CompanyFact[]
  arm: KnownArm | null
}

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
  // A parts list holding a researched arm's motor: no drivetrain question, no wheel numbers.
  const [arm, setArm] = useState<KnownArm | null>(initial?.arm ?? null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const inputsKey = (a: OpenAnswers) => JSON.stringify([a, bom, cad])
  const [readKey, setReadKey] = useState(initial ? inputsKey(initial.answers) : '')

  // The step by name, so the list can lose the drivetrain question when the arm is found.
  const [step, setStep] = useState<Step>(initial ? 'review' : 'who')
  const [back, setBack] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const steps = stepsFor(arm !== null)
  const index = steps.indexOf(step)
  const reviewAt = steps.indexOf('review')
  const question = QUESTIONS.find((q) => q.id === step)
  const go = (to: Step) => {
    setBack(steps.indexOf(to) < index)
    setStep(to)
    setError(null)
  }

  useEffect(() => {
    intake({ bom, cad, answers: null }).then((r) => {
      setFromFiles(r.specs)
      setArm(r.known_arm ?? null)
    }, console.error)
  }, [bom, cad])

  useEffect(() => onProgress({ steps, index, company, arm }), [steps, index, company, arm, onProgress])

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

  /** Check the current step and move on. */
  const next = () => {
    if (busy) return
    if (step === 'review') return finish()
    if (question?.required && !answers[question.id].trim()) return setError('Please type an answer.')
    if (steps[index + 1] === 'review') {
      if (readKey === inputsKey(answers)) return go('review') // nothing changed: keep edits
      return void work('Reading your answers', async () => {
        const result = await read()
        if (!result) return setError('Reading new answers needs the live token.')
        setSpecs(result.specs)
        setCompany(withDefaults(result.company, demo))
        setDropped(result.dropped)
        setDrafts({})
        setReadKey(inputsKey(answers))
        go('review')
      })
    }
    go(steps[index + 1])
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
      <div className="label">{step === 'review' ? 'Review' : `Question ${index + 1} of ${reviewAt}`}</div>

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
          {arm ? (
            <>
              <p className="help">
                Your parts list matches the {arm.robot}, so we did not ask about a drivetrain. A replacement motor is
                checked against these numbers, from our research on the {arm.robot}, not from your parts list.
              </p>
              <table className="specs">
                <caption>{arm.arm.joint} joint</caption>
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
                      <td>{value}</td>
                      <td>
                        <span className="src">
                          <span className="dot mid" />
                          Our research
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <>
              <p className="help">These are the numbers the job will use. Change any of them.</p>
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
          {live && !arm && (
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
            <button type="button" className="btn go" onClick={next}>
              {step === 'review' ? 'Find and Redesign' : 'OK'}
            </button>
            <span className="label hint">
              Press <kbd>Enter</kbd>
            </span>
            {index > 0 ? (
              <button type="button" className="link" onClick={() => go(steps[index - 1])}>
                Back
              </button>
            ) : (
              <>
                {example && (
                  <button type="button" className="link" onClick={() => setAnswers(example)}>
                    Use the example
                  </button>
                )}
                <button type="button" className="link" onClick={onChangeBom}>
                  Change BOM
                </button>
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}
