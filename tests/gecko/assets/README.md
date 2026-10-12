This PKCS#12 certificate and key are public synthetic loopback test fixtures.
Password: network-fixture. SAN: 127.0.0.1. They are trusted only by the integration test subclass.
`native-probe-untrusted.p12` is a second public synthetic certificate with the same
password and loopback SAN. The native-probe test core deliberately does not trust
it, so a real TLS verification failure must occur before any HTTP request.
The integration source set includes them; the production source set does not, and APK signing verification rejects their presence in production.
They must never be used for real services or release signing.
