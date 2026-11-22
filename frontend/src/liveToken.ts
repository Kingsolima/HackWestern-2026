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

/** An in-page dialog with one password field. window.prompt() is not used: embedded browsers
 * (VS Code's preview, some in-app browsers) do not support it. Resolves null on cancel. */
function promptForToken(message: string): Promise<string | null> {
  return new Promise((resolve) => {
    const dialog = document.createElement('dialog')
    dialog.className = 'token-dialog'
    const form = document.createElement('form')
    form.method = 'dialog'
    const label = document.createElement('label')
    label.textContent = message
    const input = document.createElement('input')
    input.type = 'password'
    input.autocomplete = 'off'
    label.append(input)
    const buttons = document.createElement('div')
    buttons.className = 'token-dialog-buttons'
    const ok = document.createElement('button')
    ok.className = 'primary'
    ok.value = 'ok'
    ok.textContent = 'OK'
    const cancel = document.createElement('button')
    cancel.value = 'cancel'
    cancel.textContent = 'Cancel'
    cancel.formNoValidate = true
    buttons.append(ok, cancel)
    form.append(label, buttons)
    dialog.append(form)
    dialog.addEventListener('close', () => {
      const token = dialog.returnValue === 'ok' ? input.value.trim() : ''
      dialog.remove()
      resolve(token || null)
    })
    document.body.append(dialog)
    dialog.showModal()
    input.focus()
  })
}

/** The stored token, or ask for one. null when the user cancels. */
export async function askLiveToken(message: string): Promise<string | null> {
  const token = storedLiveToken() ?? (await promptForToken(message))
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
