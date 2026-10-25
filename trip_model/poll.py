# class Poll:
#     id; question; options: list[str]
#     votes: dict[person_id, str]; closes_at; is_open
#     check_open(now) -> bool   # closes itself once closes_at has passed
#     vote(person, option, now); results() -> dict; winner() -> list[str]   # all tied options

from datetime import datetime

class Poll:
    def __init__(self, id, question, options: list[str], closes_at: datetime | None = None,
                 is_open: bool = True, votes: dict | None = None):
        self.id = id
        self.question = question
        self.options = options
        self.votes = votes if votes is not None else {}
        self.closes_at = closes_at
        self.is_open = is_open

    def close(self):
        self.is_open = False

    def check_open(self, now: datetime | None = None):
        now = now if now is not None else datetime.now()
        if self.is_open and self.closes_at is not None and now >= self.closes_at:
            self.close()
        return self.is_open

    def vote(self, person_id, option, now: datetime | None = None):
        if not self.check_open(now):
            raise ValueError("That poll is closed.")
        if option not in self.options:
            raise ValueError(f"{option!r} isn't an option. Options: {self.options}")
        self.votes[person_id] = option

    def results(self):
        result_count = {option: 0 for option in self.options}
        for vote in self.votes.values():
            result_count[vote] += 1
        return result_count

    def winner(self):
        results = self.results()
        if not self.votes:
            return []
        max_votes = max(results.values())
        winners = [option for option, count in results.items() if count == max_votes]
        return winners
