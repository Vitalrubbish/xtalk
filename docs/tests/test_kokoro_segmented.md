# Segmented Kokoro and cancellation tests

KokoroSegmentedTests uses a deterministic aiohttp synthesis peer to check submission before finish, text/date/time preservation, size/sequence bounds, cancellation isolation, actual character arrival clocks, complete words, and padding trim. Trim regressions retain internal pauses, quiet-speech guards, and punctuation tails.

IndependentDeadlineTests covers independent 300ms/1200ms defaults, invalid values, cloning, and separate first/continuation deadlines. Direct execution and unittest discovery both run all 11 tests. Interface tests complement remote conda measurements of real-model timing, audio supply, and human naturalness review.
