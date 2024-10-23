export abstract class Utils {

  
static formatDuration = (durationMs: number | undefined): string => {
    if (!durationMs) return 'Unknown';
    const seconds = Math.floor(durationMs / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    return `${hours.toString().padStart(2, '0')}:${(minutes % 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`;
  };

    // const HIGH_THRESHOLD = 1.2
  // const MINIMUM_THRESHOLD = 1.1


  static getScoreLabel = (score: number,MINIMUM_THRESHOLD:number = 1.1,HIGH_THRESHOLD:number = 1.2): string => {
    if (score < MINIMUM_THRESHOLD) return 'VERY LOW';

    const range = HIGH_THRESHOLD - MINIMUM_THRESHOLD;
    const mediumThreshold = MINIMUM_THRESHOLD + (range / 2);

    if (score >= HIGH_THRESHOLD) return 'HIGH';
    if (score >= mediumThreshold) return 'MEDIUM';
    return 'LOW';
  };

  // static getScoreLabel = (score: number, LOW_THRESHOLD: number = 1.24, HIGH_THRESHOLD: number = 1.28): string => {
  //   if (score >= HIGH_THRESHOLD) return 'SIMILAR';
  //   if (score < LOW_THRESHOLD) return 'NOT SIMILAR';
  //   return 'BORDERLINE SIMILAR';
  // };

  // static getScoreColor = (label: string): string => {
  //   switch (label) {
  //     case 'SIMILAR':
  //       return 'green';
  //     case 'BORDERLINE SIMILAR':
  //       return 'orange';
  //     case 'NOT SIMILAR':
  //       return 'red';
  //     default:
  //       return 'inherit';
  //   }
  // };

  static getScoreColor = (label: string): string => {
    switch (label) {
      case 'HIGH':
        return 'green';
      case 'MEDIUM':
        return 'orange';
      case 'LOW':
        return 'red';
      case 'VERY LOW':
        return 'gray';
      default:
        return 'inherit';
    }
  };


  static calculateSMPTETimecode(input: number, frameRate: number, isSeconds: boolean = false): string {
    let totalSeconds: number;

    if (isSeconds) {
        totalSeconds = input;
    } else {
        totalSeconds = input / frameRate;
    }

    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = Math.floor(totalSeconds % 60);
    const frames = Math.round((totalSeconds - Math.floor(totalSeconds)) * frameRate);

    const pad = (num: number): string => num.toString().padStart(2, '0');

    return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}:${pad(frames)}`;
}
}