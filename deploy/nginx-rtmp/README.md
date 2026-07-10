# Nginx RTMP

本目录预留给流媒体服务器配置。开发阶段前端使用 `VIDEO_FEED_URL` 读取视频流；接入真实 RTMP 后，可在 `.env` 中配置：

```text
RTMP_BASE_URL=rtmp://服务器地址/live
VIDEO_FEED_URL=http://后端或流媒体转码地址/demo.mjpg
```
