function resolveQueueLocation(courtsSet, customText) {
  let location = '';

  if (customText) {
    location = customText;
  } else if (courtsSet && courtsSet.size > 0) {
    const nums = Array.from(courtsSet).map(n => parseInt(n, 10)).filter(n => !isNaN(n));

    if (nums.length > 0) {
      // Rule: For sessions containing 4, 5, 7, 8, 10 with 6 or more total courts -> Two queues
      const hasCoreCluster = [4, 5, 7, 8, 10].every(c => courtsSet.has(String(c)));
      if (hasCoreCluster && courtsSet.size >= 6) {
        return '📍 - Court 4 Table & Court 7 Paddle Rack';
      }

      // Priority 1: 1, 2, 4 groupings route to Court 1 Paddle Rack
      if (courtsSet.has('1') && courtsSet.has('2') && courtsSet.has('4')) {
        location = 'Court 1 Paddle Rack';
      }
      // Priority 2: Exact single court assignment for 1, 3, 6, 7, 9, 10, 11, 12 -> "Court X Table"
      else if (nums.length === 1 && [1, 3, 6, 7, 9, 10, 11, 12].includes(nums[0])) {
        location = `Court ${nums[0]} Table`;
      }
      // Priority 3: Groups containing Court 4 & 5 or falling in Courts 4 - 6
      else if ((courtsSet.has('4') && courtsSet.has('5')) || nums.some(n => n >= 4 && n <= 6)) {
        location = 'Court 4 Table';
      }
      // Priority 4: Groups containing Court 7 / Courts 7 - 9
      else if (courtsSet.has('7') || nums.some(n => n >= 7 && n <= 9)) {
        location = 'Court 7 Paddle Rack';
      }
      // Priority 5: Courts 1 - 3
      else if (nums.some(n => n >= 1 && n <= 3)) {
        location = 'Court 1 Paddle Rack';
      }
      // Priority 6: Courts 10+
      else if (nums.some(n => n >= 10)) {
        location = 'Court 10 Paddle Rack';
      } else {
        const minCourt = Math.min(...nums);
        location = `Court ${minCourt} Paddle Rack`;
      }
    }
  }

  if (!location) return '';

  const cleanLoc = location
    .replace(/^📍\s*[-–—]?\s*/i, '')
    .replace(/^queue\s+at\s+/i, '')
    .trim();

  return `📍 - ${cleanLoc}`;
}
