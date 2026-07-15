export const ACTIVE_SESSION_KEY = 'teamchat_active_session_id'

export function getActiveSessionId() {
  const stored = localStorage.getItem(ACTIVE_SESSION_KEY)
  const id = stored ? Number(stored) : 1
  return Number.isFinite(id) && id > 0 ? id : 1
}
