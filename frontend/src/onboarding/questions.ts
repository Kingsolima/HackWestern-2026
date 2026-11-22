// The four open questions. Answers are free text: the backend reads them with Gemini and code
// confirms every value against the user's own words (backend/app/intake/extract.py).

export type QuestionId = 'who' | 'market' | 'limits' | 'drivetrain'
export type OpenAnswers = Record<QuestionId, string>

export interface Question {
  id: QuestionId
  prompt: string
  help: string
  required?: boolean
}

export const QUESTIONS: Question[] = [
  {
    id: 'who',
    prompt: 'Who are you, and what are you building?',
    help: 'Your company or team, the robot and what it does.',
    required: true,
  },
  {
    id: 'market',
    prompt: 'Who buys it, where is it assembled and where will it run?',
    help: 'Customers (any government buyers?), final assembly country, countries it is deployed in, and how much downtime hurts.',
  },
  {
    id: 'limits',
    prompt: 'What limits matter: budget, deadline, anything to avoid?',
    help: 'Parts budget per robot, when you need parts, and suppliers, countries or materials you want to stay away from.',
  },
  {
    id: 'drivetrain',
    prompt: 'What else should we know about the drivetrain?',
    help: 'Plain words and any units are fine.',
  },
]

export const EMPTY_ANSWERS: OpenAnswers = { who: '', market: '', limits: '', drivetrain: '' }

/** "a", "a and b", "a, b and c". */
export function listOf(items: string[]): string {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}
