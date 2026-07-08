import { io } from 'socket.io-client'

let socket
let activeToken = ''

export function connectAlarmStream(token, onAlarm) {
  if (!token) return null
  if (socket?.connected && activeToken === token) return socket
  if (socket) closeAlarmStream()

  activeToken = token

  socket = io('/', {
    path: '/socket.io',
    transports: ['websocket', 'polling'],
    auth: { token },
  })

  socket.on('connect', () => {
    socket.emit('subscribe', { camera_ids: ['cam-1'] })
  })

  socket.on('alarm', (payload) => {
    if (payload?.type === 'alarm_handled') return
    onAlarm(payload)
    socket.emit('ack', { alarm_id: payload.id })
  })

  return socket
}

export function closeAlarmStream() {
  if (socket) {
    socket.removeAllListeners()
    socket.close()
    socket = null
  }
  activeToken = ''
}
