const WebSocket = require('ws');
const ws = new WebSocket('ws://127.0.0.1:8000/ws/live');
ws.on('open', function open() {
  console.log('connected');
});
ws.on('message', function incoming(data) {
  console.log('received');
});
ws.on('error', function(e) {
  console.log('Error:', e);
});
