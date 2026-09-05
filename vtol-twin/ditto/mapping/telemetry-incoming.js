/*
 * Incoming payload mapper for the VTOL-1 twin (runs inside Ditto's Rhino engine: keep to ES5).
 *
 * Accepted MQTT topics (thing name is taken from the topic):
 *   vtol/<tail>/telemetry             payload: {"ts": "...", "engine": {...}, "power": {...}}  (one object per feature)
 *   vtol/<tail>/telemetry/<feature>   payload: {"ts": "...", "rpm": 5400, "egtC": 611.2}       (flat properties)
 *
 * Output: a Ditto Protocol twin MERGE command on /features (JSON merge patch), so partial updates
 * never clobber properties that were not in the message. Messages that cannot be parsed are dropped.
 */
var NAMESPACE = 'vtol.fleet';

function isObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function copyProps(src, ts) {
  var out = {};
  for (var k in src) {
    if (src.hasOwnProperty(k) && k !== 'tail' && k !== 'thingId') {
      out[k] = src[k];
    }
  }
  if (ts !== undefined && out.ts === undefined) {
    out.ts = ts;
  }
  return out;
}

function parseTopic(topic) {
  if (!topic) { return null; }
  var parts = String(topic).split('/');
  if (parts.length < 3 || parts.length > 4 || parts[0] !== 'vtol' || parts[2] !== 'telemetry') {
    return null;
  }
  return { tail: parts[1], feature: parts.length === 4 ? parts[3] : null };
}

function mapToDittoProtocolMsg(headers, textPayload, bytePayload, contentType) {
  var text = textPayload;
  if ((text === null || text === undefined) && bytePayload) {
    text = Ditto.arrayBufferToString(bytePayload);
  }
  var payload;
  try {
    payload = JSON.parse(text);
  } catch (e) {
    return null;
  }
  if (!isObject(payload)) { return null; }

  var route = parseTopic(headers['mqtt.topic']);
  if (route === null) {
    // fallback for brokers/bindings that do not expose the topic: allow the tail number in the payload
    if (payload.tail) { route = { tail: String(payload.tail), feature: payload.feature || null }; }
    else { return null; }
  }

  var features = {};
  var count = 0;
  if (route.feature !== null) {
    features[route.feature] = { properties: copyProps(payload, undefined) };
    count = 1;
  } else {
    for (var key in payload) {
      if (payload.hasOwnProperty(key) && isObject(payload[key])) {
        features[key] = { properties: copyProps(payload[key], payload.ts) };
        count++;
      }
    }
  }
  if (count === 0) { return null; }

  var dittoHeaders = {
    'content-type': 'application/merge-patch+json',
    'response-required': false
  };
  if (headers['correlation-id']) { dittoHeaders['correlation-id'] = headers['correlation-id']; }

  return Ditto.buildDittoProtocolMsg(
    NAMESPACE, route.tail, 'things', 'twin', 'commands', 'merge', '/features', dittoHeaders, features);
}
