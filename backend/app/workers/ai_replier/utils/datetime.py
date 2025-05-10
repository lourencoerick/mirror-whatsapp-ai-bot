# backend/app/utils/datetime.py

import asyncio  # Only for the example usage, not for the function itself
from datetime import datetime, timedelta, time, timezone
from loguru import logger
import math
import random

# --- Configuration Constants for Business Hours ---
BUSINESS_HOUR_START = 8  # 8 AM
BUSINESS_HOUR_END = 20  # 8 PM
WEEKEND_DAYS = [5, 6]  # Saturday (5), Sunday (6)
DEFAULT_BASE_DELAY_SECONDS = 3600  # 1 hour, for the first attempt if not specified
MAX_FOLLOW_UP_DELAY_SECONDS = 3 * 24 * 3600  # Max 3 days for a follow-up
MINIMUM_DELAY_TO_POSTPONE_TO_BUSINESS_HOURS = timedelta(seconds=10 * 60)


def calculate_follow_up_delay(
    attempt_number: int,
    base_delay_seconds: int = DEFAULT_BASE_DELAY_SECONDS,
    factor: float = 2.0,
    max_jitter_percent: float = 0.1,  # Max 10% jitter
    ensure_business_hours: bool = True,
    business_hour_start: int = BUSINESS_HOUR_START,
    business_hour_end: int = BUSINESS_HOUR_END,
    weekend_days: list[int] = list(),
) -> timedelta:
    """
    Calculates the delay for a follow-up attempt, with exponential backoff
    and optional adjustment to fall within business hours.

    Args:
        attempt_number: The current follow-up attempt number (1-indexed).
        base_delay_seconds: The base delay for the first attempt in seconds.
        factor: The multiplicative factor for exponential backoff.
        max_jitter_percent: Maximum percentage of jitter to add/subtract for randomness.
                            (e.g., 0.1 for 10%). Set to 0 for no jitter.
        ensure_business_hours: If True, adjusts the delay to ensure the follow-up
                               occurs during specified business hours and not on weekends.
        business_hour_start: The starting hour of business (e.g., 9 for 9 AM).
        business_hour_end: The ending hour of business (e.g., 18 for 6 PM).
        weekend_days: A list of weekday numbers (0=Monday, 6=Sunday) considered weekends.
                      Defaults to Saturday and Sunday.

    Returns:
        A timedelta object representing the calculated delay.
    """
    if weekend_days is None:
        weekend_days = WEEKEND_DAYS

    if attempt_number <= 0:
        attempt_number = 1

    # Calculate exponential backoff
    # For attempt 1, delay = base_delay_seconds
    # For attempt 2, delay = base_delay_seconds * factor
    # For attempt 3, delay = base_delay_seconds * factor^2
    current_delay_seconds = base_delay_seconds * (factor ** (attempt_number - 1))

    # Add jitter to avoid thundering herd or too predictable follow-ups
    if max_jitter_percent > 0:
        jitter = (
            current_delay_seconds
            * max_jitter_percent
            * (2 * math.copysign(1, 0.5 - random.random()) - 1)
        )  # random between -max_jitter_percent and +max_jitter_percent
        jitter = random.uniform(-1, 1) * current_delay_seconds * max_jitter_percent
        current_delay_seconds += jitter
        current_delay_seconds = max(0, current_delay_seconds)  # Ensure non-negative

    # Cap the delay to a maximum
    current_delay_seconds = min(current_delay_seconds, MAX_FOLLOW_UP_DELAY_SECONDS)
    calculated_delay_td = timedelta(seconds=current_delay_seconds)

    if (
        not ensure_business_hours
        or calculated_delay_td < MINIMUM_DELAY_TO_POSTPONE_TO_BUSINESS_HOURS
    ):
        logger.debug(
            f"Attempt {attempt_number}: Calculated delay (no business hours adjustment): {calculated_delay_td}"
        )
        return calculated_delay_td

    now_utc = datetime.now(timezone.utc)
    # Tentative scheduled time in UTC
    tentative_scheduled_time_utc = now_utc + calculated_delay_td

    # Adjust to business hours - this needs to be iterative as adjustments can push to next day/weekend
    final_scheduled_time_utc = tentative_scheduled_time_utc
    max_iterations = 7  # Safety break for loop, should be enough for a week
    iterations = 0

    while iterations < max_iterations:
        iterations += 1
        is_adjusted = False

        # Check for weekends
        if final_scheduled_time_utc.weekday() in weekend_days:
            days_to_add = 1
            if final_scheduled_time_utc.weekday() == weekend_days[0]:  # Saturday
                days_to_add = 2  # Move to Monday
            elif (
                final_scheduled_time_utc.weekday() == weekend_days[1]
                and len(weekend_days) > 1
            ):  # Sunday
                days_to_add = 1  # Move to Monday

            final_scheduled_time_utc = datetime(
                final_scheduled_time_utc.year,
                final_scheduled_time_utc.month,
                final_scheduled_time_utc.day,
                business_hour_start,
                0,
                0,
                tzinfo=timezone.utc,
            ) + timedelta(days=days_to_add)
            is_adjusted = True
            logger.debug(
                f"Attempt {attempt_number}: Adjusted for weekend. New tentative: {final_scheduled_time_utc}"
            )
            continue  # Re-check this new time

        # Check for before business hours
        if final_scheduled_time_utc.hour < business_hour_start:
            final_scheduled_time_utc = final_scheduled_time_utc.replace(
                hour=business_hour_start, minute=0, second=0, microsecond=0
            )
            is_adjusted = True
            logger.debug(
                f"Attempt {attempt_number}: Adjusted for before business hours. New tentative: {final_scheduled_time_utc}"
            )

        # Check for after business hours
        elif final_scheduled_time_utc.hour >= business_hour_end:
            # Move to next day, start of business hours
            final_scheduled_time_utc = datetime(
                final_scheduled_time_utc.year,
                final_scheduled_time_utc.month,
                final_scheduled_time_utc.day,
                business_hour_start,
                0,
                0,
                tzinfo=timezone.utc,
            ) + timedelta(days=1)
            is_adjusted = True
            logger.debug(
                f"Attempt {attempt_number}: Adjusted for after business hours. New tentative: {final_scheduled_time_utc}"
            )
            continue  # Re-check this new time (could be a weekend)

        if (
            not is_adjusted
        ):  # If no adjustments were made in this iteration, we are good
            break
    else:  # Max iterations reached
        logger.warning(
            f"Attempt {attempt_number}: Max iterations reached for business hours adjustment. Using last calculated: {final_scheduled_time_utc}"
        )

    # The new delay is the difference between the final adjusted time and now
    final_delay_td = final_scheduled_time_utc - now_utc

    # Ensure the final delay isn't excessively long due to adjustments, cap it again if necessary
    # (though MAX_FOLLOW_UP_DELAY_SECONDS was applied to the initial calculation)
    # This check is more about sanity after business hour adjustments.
    if (
        final_delay_td.total_seconds() > MAX_FOLLOW_UP_DELAY_SECONDS * 1.5
    ):  # Allow some leeway for BH adjustments
        logger.warning(
            f"Attempt {attempt_number}: Final delay {final_delay_td} exceeded max after BH. Capping might be needed if too large."
        )
        # Potentially cap it, or decide this is acceptable if BH logic forces it.
        # For now, we accept what BH logic produced.

    logger.info(
        f"Attempt {attempt_number}: Original calculated delay: {calculated_delay_td}. "
        f"Final delay after business hours adjustment: {final_delay_td} (Scheduled for: {final_scheduled_time_utc})"
    )
    return final_delay_td


# --- Example Usage (can be removed or kept for testing) ---
async def main_test():
    """Example of how to use the calculate_follow_up_delay function."""
    logger.info("--- Testing Follow-up Delay Calculation ---")

    print("\n--- Test Case 1: Basic Exponential Backoff (No Business Hours) ---")
    for i in range(1, 5):
        delay = calculate_follow_up_delay(
            attempt_number=i,
            ensure_business_hours=False,
            base_delay_seconds=60,
            factor=2,
            max_jitter_percent=0,
        )
        print(f"Attempt {i}: Delay = {delay}")

    print(
        "\n--- Test Case 2: With Business Hours (simulating 'now' at different times) ---"
    )

    # Simulate 'now' as Friday 17:00 UTC, next attempt should be Monday 09:00 UTC
    # For this, we'd need to mock datetime.now, or pass 'now_utc' as an argument.
    # For simplicity, let's assume 'now' is actually now and see how it behaves.

    print(f"Current time (UTC): {datetime.now(timezone.utc)}")
    for i in range(1, 4):
        # Using a small base delay to see business hour logic kick in sooner
        delay_bh = calculate_follow_up_delay(
            attempt_number=i,
            base_delay_seconds=30 * 60,  # 30 minutes
            factor=3,
            ensure_business_hours=True,
        )
        actual_trigger_time = datetime.now(timezone.utc) + delay_bh
        print(
            f"Attempt {i}: Calculated Delay = {delay_bh}, Approx. Trigger Time (UTC): {actual_trigger_time.strftime('%Y-%m-%d %H:%M:%S %Z')} ({actual_trigger_time.weekday()})"
        )
        # Simulate waiting for this delay for the next calculation (crude simulation)
        # In a real scenario, 'now_utc' would be fresh for each call.
        if i < 3:
            await asyncio.sleep(1)  # Small delay to make 'now' slightly different

    print("\n--- Test Case 3: Attempt that would fall on a weekend ---")
    # To reliably test this, we need to control 'now_utc'
    # Let's assume today is Friday. A 24-hour delay would be Saturday.
    # This test will depend on when it's run.
    # A more robust test would involve patching datetime.now().
    one_day_delay_attempt = calculate_follow_up_delay(
        attempt_number=1, base_delay_seconds=24 * 3600, ensure_business_hours=True
    )
    trigger_time_one_day = datetime.now(timezone.utc) + one_day_delay_attempt
    print(
        f"Attempt for ~24h delay: Delay = {one_day_delay_attempt}, Approx. Trigger (UTC): {trigger_time_one_day.strftime('%Y-%m-%d %H:%M:%S %Z')} ({trigger_time_one_day.weekday()})"
    )

    print("\n--- Test Case 4: Attempt that would fall late, pushing to next day ---")
    # Base delay of 1 hour, if current time is 17:30 UTC.
    late_day_attempt = calculate_follow_up_delay(
        attempt_number=1,
        base_delay_seconds=1 * 3600,
        ensure_business_hours=True,  # 1 hour
    )
    trigger_time_late_day = datetime.now(timezone.utc) + late_day_attempt
    print(
        f"Attempt for ~1h delay (if late): Delay = {late_day_attempt}, Approx. Trigger (UTC): {trigger_time_late_day.strftime('%Y-%m-%d %H:%M:%S %Z')} ({trigger_time_late_day.weekday()})"
    )


if __name__ == "__main__":
    # Setup logger for direct script execution testing
    import sys

    logger.remove()
    logger.add(sys.stderr, level="DEBUG")
    asyncio.run(main_test())
