import { io } from 'socket.io-client'

let socket

export function connectAlarmStream(token, onAlarm) {
  if (socket?.connected) return socket

  socket = io('/', {
    path: '/socket.io',
    transports: ['polling'],
    auth: { token },
  })

  socket.on('connect', () => {
    console.log('[WS] 已连接:', socket.id)
    socket.emit('subscribe', { camera_ids: [] })
  })

  socket.on('connect_error', (err) => {
    console.error('[WS] 连接错误:', err.message)
  })

  socket.on('disconnect', (reason) => {
    console.warn('[WS] 断开:', reason)
  })

  socket.on('alarm', (payload) => {
    console.log('[WS] 收到 alarm:', payload?.id, payload?.alarm_type)
    if (payload?.type === 'alarm_handled') return
    onAlarm(payload)
    socket.emit('ack', { alarm_id: payload.id })
  })

  return socket
}

export function closeAlarmStream() {
  if (socket) {
    socket.close()
    socket = null
  }
}
