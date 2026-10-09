"""Small time gate for simulated restoration; shedding is always immediate."""


class RestorationGate:
    def __init__(self, clock):
        self.clock = clock
        self.signature = None
        self.stable_since = None
        self.last_shed = None
        self.last_restored = None
        self.initialized = False
        self.applied_mask = 0

    def update(self, proposed_mask, signature, order):
        now = self.clock()
        if not self.initialized:
            self.initialized = True
            self.signature = signature
            self.stable_since = now
            self.last_shed = now
            self.last_restored = now
            self.applied_mask = proposed_mask
            return self.applied_mask
        if signature != self.signature:
            self.signature = signature
            self.stable_since = now
        shed = self.applied_mask & ~proposed_mask
        if shed:
            self.applied_mask &= proposed_mask
            self.last_shed = now
        additions = proposed_mask & ~self.applied_mask
        if (additions and now - self.stable_since >= 5 and now - self.last_shed >= 3
                and now - self.last_restored >= 1):
            bit = next((bit for bit in order if additions & (1 << bit)), None)
            if bit is not None:
                self.applied_mask |= 1 << bit
                self.last_restored = now
        return self.applied_mask
