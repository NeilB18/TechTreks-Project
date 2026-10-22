from django.contrib import admin

from trips import models as m


class PersonInline(admin.TabularInline):
    model = m.Person
    extra = 0


@admin.register(m.Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "status", "destination", "start_date", "end_date"]
    inlines = [PersonInline]


class SplitInline(admin.TabularInline):
    model = m.ExpenseSplit
    extra = 0


@admin.register(m.Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ["id", "trip", "description", "category", "paid_by", "amount_cents"]
    list_filter = ["trip", "category"]
    inlines = [SplitInline]


admin.site.register([m.Activity, m.Poll, m.Reminder, m.Refund, m.Exclusion])
