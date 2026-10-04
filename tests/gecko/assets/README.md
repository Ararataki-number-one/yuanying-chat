This PKCS#12 certificate and key are public synthetic loopback test fixtures.
Password: network-fixture. SAN: 127.0.0.1. They are trusted only by the integration test subclass.
The integration source set includes them; the production source set does not, and APK signing verification rejects their presence in production.
They must never be used for real services or release signing.
