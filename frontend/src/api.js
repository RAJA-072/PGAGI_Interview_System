const BASE_URL = 'http://localhost:8000/api'

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch (_) {
      // ignore
    }
    throw new Error(detail)
  }
  return res.json()
}

export async function fetchRoles() {
  const res = await fetch(`${BASE_URL}/roles`)
  return handle(res)
}

export async function startInterview(role, resumeFile) {
  const formData = new FormData()
  formData.append('role', role)
  formData.append('resume', resumeFile)
  const res = await fetch(`${BASE_URL}/interview/start`, {
    method: 'POST',
    body: formData,
  })
  return handle(res)
}

export async function submitAnswer(sessionId, answer) {
  const res = await fetch(`${BASE_URL}/interview/${sessionId}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer }),
  })
  return handle(res)
}

export async function fetchSummary(sessionId) {
  const res = await fetch(`${BASE_URL}/interview/${sessionId}/summary`)
  return handle(res)
}
