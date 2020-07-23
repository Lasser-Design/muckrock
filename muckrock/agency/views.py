"""
Views for the Agency application
"""

# Django
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.db.models.aggregates import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import linebreaks
from django.views.generic.edit import FormView

# Standard Library
import re

# Third Party
from dal import autocomplete
from fuzzywuzzy import fuzz, process

# MuckRock
from muckrock.agency.filters import AgencyFilterSet
from muckrock.agency.forms import AgencyMergeForm
from muckrock.agency.models import Agency
from muckrock.agency.utils import initial_communication_template
from muckrock.core.views import MRAutocompleteView, MRSearchFilterListView
from muckrock.jurisdiction.forms import FlagForm
from muckrock.jurisdiction.models import Jurisdiction
from muckrock.jurisdiction.views import collect_stats
from muckrock.task.models import FlaggedTask, ReviewAgencyTask


class AgencyList(MRSearchFilterListView):
    """Filterable list of agencies"""

    model = Agency
    filter_class = AgencyFilterSet
    title = "Agencies"
    template_name = "agency/list.html"
    default_sort = "name"
    sort_map = {"name": "name", "jurisdiction": "jurisdiction__slug"}

    def get_queryset(self):
        """Limit agencies to only approved ones."""
        approved = super(AgencyList, self).get_queryset().get_approved()
        approved = approved.select_related(
            "jurisdiction", "jurisdiction__parent", "jurisdiction__parent__parent"
        )
        return approved


def detail(request, jurisdiction, jidx, slug, idx):
    """Details for an agency"""

    agency = get_object_or_404(
        Agency.objects.select_related(
            "jurisdiction", "jurisdiction__parent", "jurisdiction__parent__parent"
        ),
        jurisdiction__slug=jurisdiction,
        jurisdiction__pk=jidx,
        slug=slug,
        pk=idx,
        status="approved",
    )

    foia_requests = agency.get_requests()
    foia_requests = (
        foia_requests.get_viewable(request.user)
        .filter(agency=agency)
        .select_related("agency__jurisdiction__parent__parent")
        .order_by("-composer__datetime_submitted")[:10]
    )

    if request.method == "POST":
        action = request.POST.get("action")
        form = FlagForm(request.POST)
        if action == "flag":
            if form.is_valid() and request.user.is_authenticated:
                FlaggedTask.objects.create(
                    user=request.user,
                    text=form.cleaned_data.get("reason"),
                    agency=agency,
                )
                messages.success(request, "Correction submitted. Thanks!")
                return redirect(agency)
        elif action == "review" and request.user.is_staff:
            task = ReviewAgencyTask.objects.ensure_one_created(
                agency=agency, resolved=False
            )
            messages.success(request, "Agency marked for review.")
            return redirect(reverse("review-agency-task", kwargs={"pk": task.pk}))
    else:
        form = FlagForm()

    context = {
        "agency": agency,
        "foia_requests": foia_requests,
        "form": form,
        "sidebar_admin_url": reverse("admin:agency_agency_change", args=(agency.pk,)),
    }

    collect_stats(agency, context)

    return render(request, "profile/agency.html", context)


def redirect_old(request, jurisdiction, slug, idx, action):
    """Redirect old urls to new urls"""
    # pylint: disable=unused-variable
    # pylint: disable=unused-argument

    # some jurisdiction slugs changed, just ignore the jurisdiction slug passed in
    agency = get_object_or_404(Agency, pk=idx)
    jurisdiction = agency.jurisdiction.slug
    jidx = agency.jurisdiction.pk

    if action == "view":
        return redirect(
            "/agency/%(jurisdiction)s-%(jidx)s/%(slug)s-%(idx)s/" % locals()
        )

    return redirect(
        "/agency/%(jurisdiction)s-%(jidx)s/%(slug)s-%(idx)s/%(action)s/" % locals()
    )


def redirect_flag(request, jurisdiction, jidx, slug, idx):
    # pylint: disable=unused-argument
    """Redirect flag urls to base agency"""
    return redirect("agency-detail", jurisdiction, jidx, slug, idx)


def boilerplate(request):
    """Return the boilerplate language for requests to the given agency"""

    p_new = re.compile(r"\$new\$[^$]+\$[0-9]+\$")
    p_int = re.compile(r"[0-9]+")
    agency_pks = request.GET.getlist("agencies")
    new_agency_pks = [a for a in agency_pks if p_new.match(a)]
    other_agency_pks = [a for a in agency_pks if p_int.match(a)]

    agencies = Agency.objects.filter(pk__in=other_agency_pks)
    extra_jurisdictions = Jurisdiction.objects.filter(
        pk__in=[i.split("$")[3] for i in new_agency_pks]
    )
    if request.user.is_authenticated:
        user_name = request.user.profile.full_name
    else:
        user_name = (
            '<abbr class="tooltip" title="This will be replaced by your full '
            'name">{ name }</abbr>'
        )
    split_token = "$split$"
    text = initial_communication_template(
        agencies,
        user_name,
        split_token,
        extra_jurisdictions=extra_jurisdictions,
        edited_boilerplate=False,
        proxy=False,
        html=True,
    )
    intro, outro = text.split(split_token)
    return JsonResponse(
        {"intro": linebreaks(intro.strip()), "outro": linebreaks(outro.strip())}
    )


def contact_info(request, idx):
    """Return the agencies contact info"""
    agency = get_object_or_404(Agency, pk=idx)
    if not request.user.has_perm("foia.set_info_foiarequest"):
        if agency.portal:
            type_ = "portal"
        elif agency.email:
            type_ = "email"
        elif agency.fax:
            type_ = "fax"
        elif agency.address:
            type_ = "snail"
        else:
            type_ = "none"
        return JsonResponse({"type": type_})
    else:
        return JsonResponse(
            {
                "portal": {
                    "type": agency.portal.get_type_display(),
                    "url": agency.portal.url,
                }
                if agency.portal
                else None,
                "emails": [
                    {"value": e.pk, "display": str(e)}
                    for e in agency.emails.filter(status="good").exclude(
                        email__endswith="muckrock.com"
                    )
                ],
                "faxes": [
                    {"value": f.pk, "display": str(f)}
                    for f in agency.phones.filter(status="good", type="fax")
                ],
                "email": str(agency.email)
                if agency.email and agency.email.status == "good"
                else None,
                "cc_emails": [str(e) for e in agency.other_emails],
                "fax": str(agency.fax)
                if agency.fax and agency.fax.status == "good"
                else None,
                "address": str(agency.address) if agency.address else None,
            }
        )


class MergeAgency(PermissionRequiredMixin, FormView):
    """View to merge agencies together"""

    form_class = AgencyMergeForm
    template_name = "agency/merge.html"
    permission_required = "agency.merge_agency"

    def get_initial(self):
        """Set initial choice based on get parameter"""
        initial = super(MergeAgency, self).get_initial()
        if "bad_agency" in self.request.GET:
            initial["bad_agency"] = self.request.GET["bad_agency"]
        return initial

    def form_valid(self, form):
        """Confirm and merge"""
        if form.cleaned_data["confirmed"]:
            good = form.cleaned_data["good_agency"]
            bad = form.cleaned_data["bad_agency"]
            good.merge(bad, self.request.user)
            messages.success(self.request, "Merged {} into {}!".format(good, bad))
            return redirect("agency-merge")
        else:
            initial = {
                "good_agency": form.cleaned_data["good_agency"],
                "bad_agency": form.cleaned_data["bad_agency"],
            }
            form = self.form_class(confirmed=True, initial=initial)
            return self.render_to_response(self.get_context_data(form=form))

    def form_invalid(self, form):
        """Something went wrong"""
        messages.error(self.request, form.errors)
        return redirect("agency-merge")

    def handle_no_permission(self):
        """What to do if the user does not have permisson to view this page"""
        messages.error(self.request, "You do not have permission to view this page")
        return redirect("index")


class AgencyAutocomplete(MRAutocompleteView):
    """Autocomplete for picking agencies"""

    queryset = Agency.objects.filter(status="approved").select_related("jurisdiction")
    search_fields = [
        "name",
        "aliases",
        "jurisdiction__name",
        "=jurisdiction__abbrev",
        "=jurisdiction__parent__abbrev",
    ]
    split_words = "and"
    template = "autocomplete/agency.html"

    def get_queryset(self):
        """Filter by jurisdiction"""

        queryset = super().get_queryset()
        queryset = self._filter_by_jurisdiction(queryset)

        return queryset

    def _filter_by_jurisdiction(self, queryset):
        """If a jurisdiction is forwarded, filter by it"""
        if "jurisdiction" not in self.forwarded:
            return queryset

        # jurisdiction is forwarded as a list, so grab first element
        try:
            jurisdiction_id = self.forwarded["jurisdiction"][0]
        except (TypeError, IndexError):
            # if jurisdiction is not a single element list, something went wrong
            # do not filter
            return queryset

        appeal = self.forwarded.get("appeal", False)
        if appeal:
            jurisdiction = Jurisdiction.objects.get(pk=jurisdiction_id)
            if jurisdiction.level == "l":
                # For local jurisdictions, appeal agencies may come from the
                # parent level
                return queryset.filter(
                    jurisdiction_id__in=(jurisdiction.pk, jurisdiction.parent_id)
                )

        # otherwise just get agencies from the given jurisdiction
        return queryset.filter(jurisdiction=jurisdiction_id)


class AgencyComposerAutocomplete(AgencyAutocomplete):
    """Autocomplete for picking agencies with fuzzy matching and new agency creation"""

    queryset = Agency.objects.select_related("jurisdiction__parent").only(
        "name",
        "exempt",
        "exempt_note",
        "requires_proxy",
        "uncooperative",
        "status",
        "jurisdiction__name",
        "jurisdiction__level",
        "jurisdiction__parent__abbrev",
    )

    def get_queryset(self):
        """Filter by jurisdiction"""

        queryset = super().get_queryset()
        queryset = (
            queryset.get_approved_and_pending(self.request.user)
            .annotate(count=Count("foiarequest"))
            .order_by("-count")[:10]
        )

        query, jurisdiction = self._split_jurisdiction(self.q)
        fuzzy_choices = self._fuzzy_choices(query, jurisdiction)

        return (
            self.queryset.filter(
                pk__in=[a.pk for a in queryset] + [a[2].pk for a in fuzzy_choices]
            )
            .annotate(count=Count("foiarequest"))
            .order_by("-count")
        )

    def _split_jurisdiction(self, query):
        """Try to pull a jurisdiction out of an unmatched query"""
        comma_split = query.split(",")
        if len(comma_split) > 2:
            # at least 2 commas, assume last 2 parts are locality, state
            locality, state = [w.strip() for w in comma_split[-2:]]
            name = ",".join(comma_split[:-2])
            try:
                jurisdiction = Jurisdiction.objects.get(
                    Q(parent__name__iexact=state) | Q(parent__abbrev__iexact=state),
                    name__iexact=locality,
                    level="l",
                )
                return name, jurisdiction
            except Jurisdiction.DoesNotExist:
                pass
        if len(comma_split) > 1:
            # at least 1 commas, assume the last part is a jurisdiction
            state = comma_split[-1].strip()
            name = ",".join(comma_split[:-1])
            try:
                # first see if it matches a state
                jurisdiction = Jurisdiction.objects.get(
                    Q(name__iexact=state) | Q(abbrev__iexact=state), level="s"
                )
                return name, jurisdiction
            except Jurisdiction.DoesNotExist:
                # if not, try matching a locality
                # order them by popularity
                jurisdiction = (
                    Jurisdiction.objects.filter(name__iexact=state, level="l")
                    .annotate(count=Count("agencies__foiarequest"))
                    .order_by("-count")
                    .first()
                )
                if jurisdiction is not None:
                    return name, jurisdiction

        # if all else fails, assume they want a federal agency
        return query, Jurisdiction.objects.get(level="f")

    def _fuzzy_choices(self, query, jurisdiction):
        """Do fuzzy matching for additional choices"""
        choices = self.queryset.get_approved_and_pending(self.request.user).filter(
            jurisdiction=jurisdiction
        )
        return process.extractBests(
            query,
            {a: a.name for a in choices},
            scorer=fuzz.partial_ratio,
            score_cutoff=83,
            limit=10,
        )
