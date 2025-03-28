/**
 * Formats a message timestamp based on the following rules:
 * - If the message is from today, returns the time in "HH:mm" (24-hour format).
 * - If the message is from yesterday, returns "Ontem".
 * - If the message is from 2 to 4 days ago, returns the weekday name in Portuguese.
 * - If the message is older than 4 days, returns the date in "DD/MM/YYYY" format.
 *
 * @param timestamp - The timestamp of the message (as a Date or string convertible to Date).
 * @returns A formatted string representing the message date/time.
 */
export function formatLastMessageAt(utcTimestamp: Date | string): string {
    // Convert the input to a Date object if it's not already
    const messageUtcDateObj = typeof utcTimestamp === 'string' ? new Date(utcTimestamp) : utcTimestamp;
    
    // convert the date to local timezone
    const messageDateObj = new Date(
      messageUtcDateObj.getTime() - messageUtcDateObj.getTimezoneOffset() * 60000
    );  
    
    // Get current date and set both dates to midnight for proper day comparison
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const messageDate = new Date(
      messageDateObj.getFullYear(),
      messageDateObj.getMonth(),
      messageDateObj.getDate()
    );
  
    // Calculate difference in full days between today and the message date
    const diffMs = today.getTime() - messageDate.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 3600 * 24));
  
    if (diffDays === 0) {
      // Same day: return the time in HH:mm format (24-hour)
      return messageDateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
    } else if (diffDays === 1) {
      // Yesterday
      return "Ontem";
    } else if (diffDays >= 2 && diffDays <= 4) {
      // For 2 to 4 days ago, return the weekday in Portuguese
      // Note: getDay() returns 0 for Sunday, 1 for Monday, etc.
      const weekdayMap: { [key: number]: string } = {
        0: "domingo",
        1: "segunda-feira",
        2: "terça-feira",
        3: "quarta-feira",
        4: "quinta-feira",
        5: "sexta-feira",
        6: "sábado"
      };
      return weekdayMap[messageDateObj.getDay()];
    } else {
      // More than 4 days ago: return the date in DD/MM/YYYY format
      const day = messageDateObj.getDate().toString().padStart(2, '0');
      const month = (messageDateObj.getMonth() + 1).toString().padStart(2, '0');
      const year = messageDateObj.getFullYear();
      return `${day}/${month}/${year}`;
    }
  }
  