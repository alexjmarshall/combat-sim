export function rand() {
  return Math.random();
}

export function randint(lo, hi) {
  return Math.floor(Math.random() * (hi - lo + 1)) + lo;
}

export function rollSuccesses(n) {
  let count = 0;
  for (let i = 0; i < n; i++) {
    if (Math.floor(Math.random() * 6) + 1 >= 5) count++;
  }
  return count;
}
