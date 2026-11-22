// The live token (X-Live-Token): asked once per tab and kept in sessionStorage. Real TinyFish and
// Gemini calls spend credit, so the public deploy wants it for anything that is not a replay.

const TOKEN_KEY = 'live-jobs-token'

export function storedLiveToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null // storage blocked: just ask every time
  }
}

/** The stored token, or ask for one. null when the user cancels. */
export function askLiveToken(message: string): string | null {
  const token = storedLiveToken() ?? window.prompt(message)
  if (!token) return null
  try {
    sessionStorage.setItem(TOKEN_KEY, token)
  } catch {
    // ignore
  }
  return token
}

export function forgetLiveToken() {
  try {
    sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // ignore
  }
}
