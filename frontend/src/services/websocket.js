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
    socket.emit('subscribe', { camera_ids: ['cam-1', 'cam-2'] })
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
    socket.close()
    socket = null
  }
}
