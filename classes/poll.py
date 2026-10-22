# class Poll:
#     id; question; options: list[str]
#     votes: dict[person_id, str]; closes_at; is_open
#     vote(person, option); results() -> dict; winner() -> list[str]   # all tied options

from datetime import datetime

class Poll:
    def __init__(self, id, question, options: list[str], closes_at: datetime | None = None,
                 is_open: bool = True):
        self.id = id
        self.question = question
        self.options = options
        self.votes = {}
        self.closes_at = closes_at
        self.is_open = is_open

    def close(self):
        self.is_open = False

    def check_open(self, now: datetime | None = None):
        now = now if now is not None else datetime.now()
        if self.is_open and self.closes_at is not None and now >= self.closes_at:
            self.close()
        return self.is_open

    def vote(self, person_id, option):
        if not self.check_open():
            raise ValueError("Poll is closed.")
        if option not in self.options:
            raise ValueError("Invalid option.")
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
