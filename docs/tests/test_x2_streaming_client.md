# X2 client tests

Verify 80 ms input hints, distinct pause/EOF requests and direct online transcript delivery.

F1 uses deferred HTTP results with the real ASRManager and MicroTurnAssembler. Tests cover same-tick delivery without further audio, empty first and unchanged windows, exactly one read per tick with no independent polling, preservation of partial audio, no EOF from reads, and cleanup of in-flight reads on cancellation/shutdown.
