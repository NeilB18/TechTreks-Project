import unittest
from datetime import datetime, timedelta
from itertools import count

from classes.activity import Activity
from classes.budget import Budget
from classes.category import Category
from classes.expense import Expense
from classes.person import Person
from classes.poll import Poll
from classes.reminder import Reminder
from classes.trip import Trip

expense_ids = count(1)

def make_expense(paid_by, amount_cents, category=Category.FOOD):
    return Expense(next(expense_ids), paid_by, amount_cents, "test", category)

def make_trip(*names):
    trip = Trip(1, "Spring Break")
    people = [Person(name, name.title(), f"chat-{name}", f"@{name}") for name in names]
    for person in people:
        trip.add_member(person)
    return trip, people


class TestExpenseSplits(unittest.TestCase):
    def setUp(self):
        self.x = Person("x", "X", "cx", "@x")

    def test_equal_split_including_payer(self):
        e = make_expense(self.x, 9000)
        self.assertEqual(e.split_equal(["x", "y", "z"]), {"x": 6000, "y": -3000, "z": -3000})

    def test_equal_split_payer_not_participant(self):
        e = make_expense(self.x, 9000)
        self.assertEqual(e.split_equal(["y", "z"]), {"x": 9000, "y": -4500, "z": -4500})

    def test_custom_split(self):
        e = make_expense(self.x, 1700)
        self.assertEqual(e.split_custom({"x": 800, "y": 600, "z": 300}),
                         {"x": 900, "y": -600, "z": -300})

    def test_equal_split_remainder_goes_to_first_ids(self):
        e = make_expense(self.x, 1000)
        e.split_equal(["z", "y", "x"])
        self.assertEqual([e.share_of(p) for p in ["x", "y", "z"]], [334, 333, 333])

    def test_percentage_split(self):
        e = make_expense(self.x, 1000)
        e.split_percentage({"x": 33.33, "y": 33.33, "z": 33.34})
        self.assertEqual([e.share_of(p) for p in ["x", "y", "z"]], [333, 333, 334])
        self.assertEqual(sum(e.splits.values()), 0)

    def test_percentage_must_sum_to_100(self):
        with self.assertRaises(ValueError):
            make_expense(self.x, 1000).split_percentage({"x": 50, "y": 40})

    def test_custom_must_cover_whole_bill(self):
        with self.assertRaises(ValueError):
            make_expense(self.x, 1000).split_custom({"y": 500})

    def test_duplicate_participants_rejected(self):
        with self.assertRaises(ValueError):
            make_expense(self.x, 1000).split_equal(["y", "y"])


class TestBudget(unittest.TestCase):
    def test_remaining_and_warning(self):
        trip, (a, b) = make_trip("a", "b")
        budget = Budget("a", 50000, {Category.DRINKS: 8000})
        e = make_expense(b, 15000, Category.DRINKS)
        e.split_equal(["a", "b"])  # a's share is 7500
        trip.add_expense(e)
        self.assertEqual(budget.remaining(Category.DRINKS, trip.expenses), 500)
        self.assertTrue(budget.warning(Category.DRINKS, trip.expenses))

    def test_planned_costs_count_toward_warning(self):
        budget = Budget("a", 50000, {Category.ACTIVITIES: 14000})
        self.assertFalse(budget.warning(Category.ACTIVITIES, []))
        self.assertFalse(budget.warning(Category.ACTIVITIES, [], planned_cents=10000))
        self.assertTrue(budget.warning(Category.ACTIVITIES, [], planned_cents=13333))

    def test_no_limit_returns_none(self):
        budget = Budget("a", 50000, {})
        self.assertIsNone(budget.remaining(Category.FOOD, []))
        self.assertFalse(budget.warning(Category.FOOD, []))


class TestTripLedger(unittest.TestCase):
    def test_balances_and_settlement_excluded_from_spending(self):
        trip, (x, y, z) = make_trip("x", "y", "z")
        e = make_expense(x, 9000)
        e.split_equal(["x", "y", "z"])
        trip.add_expense(e)
        self.assertEqual(trip.balances(), {"x": 6000, "y": -3000, "z": -3000})

        trip.record_settlement("y", "x", 3000, "pay-1")
        self.assertEqual(trip.balances(), {"x": 3000, "y": 0, "z": -3000})
        self.assertEqual(trip.spent_by_category()[Category.FOOD], 9000)
        self.assertNotIn(Category.SETTLEMENT, trip.spent_by_category())
        self.assertEqual(trip.spent_by_category(y)[Category.FOOD], 3000)
        self.assertEqual(trip.settlement_plan(), [("z", "x", 3000)])

    def test_settlement_idempotent(self):
        trip, _ = make_trip("x", "y")
        trip.record_settlement("y", "x", 100, "pay-1")
        with self.assertRaises(ValueError):
            trip.record_settlement("y", "x", 100, "pay-1")

    def test_expense_with_non_member_rejected(self):
        trip, (x, _) = make_trip("x", "y")
        e = make_expense(x, 1000)
        e.split_equal(["x", "stranger"])
        with self.assertRaises(ValueError):
            trip.add_expense(e)

    def test_greedy_settlements_pairs_exact_opposites_first(self):
        trip, _ = make_trip()
        # a and b cancel exactly, so they settle directly and c covers d and e: 3 payments.
        b = {"a": -500, "b": 500, "c": -700, "d": 300, "e": 400}
        payments = trip._greedy_settlements(b)
        self.assertEqual(payments, [("a", "b", 500), ("c", "e", 400), ("c", "d", 300)])

    def test_greedy_settlements_clears_everyone(self):
        trip, _ = make_trip()
        b = {"a": -1000, "b": -600, "c": 900, "d": 500, "e": 200}
        payments = trip._greedy_settlements(b)
        self.assertLessEqual(len(payments), len(b) - 1)
        net = dict.fromkeys(b, 0)
        for debtor, creditor, amount in payments:
            self.assertLess(b[debtor], 0)
            self.assertGreater(b[creditor], 0)
            net[debtor] += amount
            net[creditor] -= amount
        self.assertEqual({p: -v for p, v in net.items()}, b)

    def test_empty_plan(self):
        trip, _ = make_trip("x", "y")
        self.assertEqual(trip.settlement_plan(), [])


class TestPlanning(unittest.TestCase):
    def test_itinerary_by_day(self):
        trip, (x, _) = make_trip("x", "y")
        day = datetime(2027, 3, 10, 9)
        late = Activity(2, "Dinner", "Downtown", day + timedelta(hours=10),
                        day + timedelta(hours=12), 3000, True, [x], False, None)
        early = Activity(1, "Hike", "Trail", day, day + timedelta(hours=3),
                         0, False, [x], True, None)
        trip.add_activity(late)
        trip.add_activity(early)
        self.assertEqual(trip.itinerary_by_day(), {day.date(): [early, late]})

    def test_poll_ties_and_closing(self):
        poll = Poll(1, "Where?", ["Miami", "Denver"])
        self.assertEqual(poll.winner(), [])
        poll.vote("x", "Miami")
        poll.vote("y", "Denver")
        self.assertEqual(poll.winner(), ["Miami", "Denver"])
        poll.vote("y", "Miami")
        self.assertEqual(poll.winner(), ["Miami"])

        closed = Poll(2, "When?", ["March"], closes_at=datetime.now() - timedelta(minutes=1))
        with self.assertRaises(ValueError):
            closed.vote("x", "March")

    def test_reminder_validation(self):
        with self.assertRaises(ValueError):
            Reminder("Pack!", datetime.now(), created_by="bob")
        self.assertEqual(Reminder("Pack!", datetime.now(), created_by="agent").created_by, "agent")
        r = Reminder("Pack!", datetime.now() - timedelta(minutes=1))
        self.assertTrue(r.is_due())
        r.mark_sent()
        self.assertFalse(r.is_due())


if __name__ == "__main__":
    unittest.main()
