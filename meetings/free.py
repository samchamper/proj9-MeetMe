# Implementation of function to find blocks of free time given a
# list of events and some other parameters.
# Author: Sam Champer

import arrow


def free(e_list, op_hr, op_min, c_hr, c_min, day_range, min_len):
    """
    Return a list of free times
    :param e_list: a list of events that block free times.
    :param op_hr: The earliest time of day that counts as free.
    :param op_min: min for op_hr
    :param c_hr: The time of day after which we do not count as free.
    :param c_min: min for c_hr.
    :param day_range: The range of days to find free time in.
    :param min_len: The minimum length of time a window of free time has to be in order to qualify for listing.
    :return: list of windows of free time (each window is a list with two elements: window_open and window_close).
    """
    local_event_list = e_list[:]  # A local copy to mess with.
    # Step one: we can't meet outside the selected time windows,
    # so block those windows of time out, then add them to our busy times.
    add_nights_to_busy(local_event_list, op_hr, op_min, c_hr, c_min, day_range)
    local_event_list.sort(key=lambda i: arrow.get(i[1]))

    # Step two: merge overlapping events on the event list into single events.
    merged_list = merge_events(local_event_list)

    # Step three: each window of time between merged events that is longer than
    # minimum length is a window of time in which a meeting can be scheduled, so
    # add them to a list, and return.
    freetimes_list = free_list(merged_list, day_range)
    crop = crop_list(freetimes_list, min_len)

    return crop


def add_nights_to_busy(e_list, op_hr, op_min, c_hr, c_min, day_range):
    """
    Add times that are beyond our specified time range to the busy list
    :param e_list: The list of events in the form of a list with three strings:
            the first is the event name, the next are iso format times for start and finish.
    :param op_hr: start of daily acceptable window
    :param op_min: start of daily acceptable window
    :param c_hr: end of daily acceptable window
    :param c_min: end of daily acceptable window
    :param day_range: list of arrow objects
    :return: the list with the blocked out times added.
    """
    open_time = float(op_hr) + op_min / 60
    close_time = float(c_hr) + c_min / 60
    td = 24- (close_time - open_time)
    prev_day = day_range[0].shift(days=-1)
    # Start by blocking out the time for the previous day, to cover the case
    # that the first closed period starts the previous day (example: people
    # not available at night).
    # The blocked out time opens when the available time closes!
    block_time_op = prev_day.shift(hours=+close_time)
    # The blocked time goes for td hours.
    block_time_close = block_time_op.shift(hours=+td)
    block = ["Not available", block_time_op.isoformat(), block_time_close.isoformat()]
    e_list.append(block)
    for i in day_range:
        block_time_op = i.shift(hours=+close_time)
        block_time_close = block_time_op.shift(hours=+td)
        block = ["Not available", block_time_op.isoformat(), block_time_close.isoformat()]
        e_list.append(block)


def merge_events(events):
    """
    :param events: a list of events
    :return: a list of events with all
    overlapping and immediately abutting
    events merged into single events.
    """
    arrow_list = []
    for i in events:
        arrow_list.append([arrow.get(i[1]), arrow.get(i[2])])

    new_list = []
    block_start = arrow_list[0][0]
    block_end = arrow_list[0][1]
    index = 1
    while index < len(arrow_list) - 1:
        while arrow_list[index][0] <= block_end:
            # Look through events until past the block of overlapping ones.
            block_end = max([block_end, arrow_list[index][1]])
            index += 1
            if index > len(arrow_list) - 1:
                break
        if index > len(arrow_list) - 1:
            break  # In this case, the final item is part of the prev block.
        # Append the block and prime a new block.
        new_list.append([block_start, block_end])
        block_start = arrow_list[index][0]
        block_end = arrow_list[index][1]
        index += 1
    # Done going through the list. Append the final item.
    new_list.append([block_start, block_end])

    return new_list


def free_list(busy, day_range):
    """
    With the list of events now in sorted order and not overlapping,
    the free times are simply the times between the events.
    The only cases that need to be considered are the first window of
    free time and the last window of free time, which may be cut by the
    absolute opening time of the time window under consideration or the
    absolute close time
    :param busy: a list of events (each consisting of two arrow objects).
    :param day_range: a list of days, arrow objects.
    :return: a list of free times (each consisting of two arrow objects
    """
    list_of_free_times = []

    index = 0
    # Special case for first window of free time.
    if busy[0][0] < day_range[0] < busy[0][1]:
        # Midnight of start day is inside the first busy period,
        # So the first free window starts after busy period 1:
        free_open = busy[0][1]
        index += 1
    elif day_range[0] > busy[0][0] and day_range[0] > busy[0][1]:
        # In this case, the first busy period is entirely before
        # the time window, so it's garbage. Index past it.
        free_open = day_range[0]
        index += 1
    else:
        # Available window starts at midnight, don't index past event.
        free_open = day_range[0]

    while index < len(busy):
        free_close = busy[index][0]  # Event starts, free window closes.
        list_of_free_times.append([free_open, free_close])
        free_open = busy[index][1]
        index += 1

    # Final cleanup: if the last free_open is before midnight on the
    # last day, then midnight on the last day is free_close. If free_open
    # is after midnight on the last day, then it is trash
    # so we need do nothing.
    if free_open < day_range[-1]:
        free_close = day_range[-1]
        list_of_free_times.append([free_open, free_close])

    return list_of_free_times


def crop_list(timelist, min_len):
    """
    Crop out items shorter than min len
    """
    croped_list = []
    for i in timelist:
        if i[0].shift(minutes=+min_len) <= i[1]:
            croped_list.append(i)
    return croped_list
