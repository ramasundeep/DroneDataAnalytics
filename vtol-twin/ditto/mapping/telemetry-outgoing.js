/*
 * Outgoing mapper: not used by the events target (which publishes plain Ditto Protocol JSON),
 * but the JavaScript mapping engine requires both directions to be defined.
 * Passes the Ditto Protocol message through unchanged.
 */
function mapFromDittoProtocolMsg(namespace, name, group, channel, criterion, action, path, dittoHeaders, value, status, extra) {
  var msg = Ditto.buildDittoProtocolMsg(namespace, name, group, channel, criterion, action, path, dittoHeaders, value, status, extra);
  return Ditto.buildExternalMsg(dittoHeaders, JSON.stringify(msg), null, 'application/vnd.eclipse.ditto+json');
}
