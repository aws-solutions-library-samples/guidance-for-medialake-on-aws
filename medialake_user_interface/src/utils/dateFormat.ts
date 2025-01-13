export function formatDate(dateString: string): string {
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) {
            return 'Invalid Date';
        }
        return new Intl.DateTimeFormat('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        }).format(date);
    } catch (error) {
        console.error('Error formatting date:', error);
        return 'Invalid Date';
    }
}
