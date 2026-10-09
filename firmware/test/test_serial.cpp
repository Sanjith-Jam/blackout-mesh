#include "session.h"
#include <assert.h>
#include <stdio.h>
#include <initializer_list>
using namespace mesh;
int main() {
  Framer frame; HostMessage message;
  assert(parseHost("{\"v\":2,\"type\":\"hello\"}", message));
  for (const char* invalid : {"{}", "[]", "null", "{", "{\"v\":2,\"type\":\"hello\"}junk", "{\"v\":true,\"type\":\"hello\"}",
       "{\"v\":2,\"type\":\"hello\",\"extra\":0}",
       "{\"v\":2,\"type\":\"set_loads\",\"boot\":1,\"epoch\":1,\"session\":1,\"seq\":1,\"target\":1,\"mask\":512}",
       "{\"v\":2,\"type\":\"sync\",\"boot\":1,\"epoch\":1,\"session\":1,\"selected\":\"D\"}"})
    assert(!parseHost(invalid, message));
  for (int i = 0; i < 513; ++i) assert(!frame.feed('x'));
  assert(frame.feed('\n') == -1);
  assert(!frame.feed('{')); assert(!frame.feed('}')); assert(frame.feed('\n') == 1);
  assert(!parseHost(frame.data, message));
  assert(parseHost("{\"v\":2,\"type\":\"sync\",\"boot\":99,\"epoch\":1,\"session\":10,\"selected\":\"B\"}", message));
  Session host(99, 9);
  assert(host.sync(message, 0) && host.input.selected == 'B');
  assert(!host.sync(message, 0));
  auto event = host.event(1); assert(event && host.acknowledge(event));
  assert(!host.acknowledge(event));
  event = host.event(2); assert(!host.eventTimeout(1001) && host.eventTimeout(1002));
  assert(host.stale(1500)); host.disconnect();
  assert(!host.context(message) && !host.event(1501));
  assert(!host.sync(message, 1501)); message.epoch = 2;
  assert(host.sync(message, 1502)); assert(!host.acknowledge(event));
  assert(host.event(1503) > event);
  puts("serial/session assertions passed");
}
