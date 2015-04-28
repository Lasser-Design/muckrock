"""
Comm helper functions for FOIA views
"""

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.validators import validate_email, ValidationError
from django.http import HttpResponse, Http404
from django.shortcuts import redirect, get_object_or_404

from datetime import datetime

from muckrock.foia.models import FOIACommunication

# pylint: disable=too-many-arguments
def save_foia_comm(request, foia, from_who, comm, message, formset=None, appeal=False, snail=False):
    """Save the FOI Communication"""
    comm = FOIACommunication.objects.create(
        foia=foia,
        from_who=from_who,
        to_who=foia.get_to_who(),
        date=datetime.now(),
        response=False,
        full_html=False,
        communication=comm
    )
    if formset is not None:
        foia_files = formset.save(commit=False)
        for foia_file in foia_files:
            foia_file.comm = comm
            foia_file.title = foia_file.name()
            foia_file.date = comm.date
            foia_file.save()
    foia.submit(appeal=appeal, snail=snail)
    messages.success(request, message)

@user_passes_test(lambda u: u.is_staff)
def move_comm(request, next_):
    """Admin moves a communication to a different FOIA"""
    try:
        comm = FOIACommunication.objects.get(pk=request.POST['comm_pk'])
        new_foia_pks = request.POST['new_foia_pk_%s' % comm_pk].split(',')
        comm.move(new_foia_pks)
        msg = 'Communication moved to the following requests: '
        # TODO: Link to the FOIAs indicated by the PKs
        # href = lambda f: '<a href="%s">%s</a>' % (f.get_absolute_url(), f.pk)
        msg += ', '.join(new_foia_pks)
        messages.success(request, msg)
    except (KeyError, FOIACommunication.DoesNotExist):
        messages.error(request, 'The communication does not exist.')
    except ValueError:
        messages.error(request, 'No move destination provided.')
    return redirect(next_)

@user_passes_test(lambda u: u.is_staff)
def delete_comm(request, next_):
    """Admin deletes a communication"""
    try:
        comm = FOIACommunication.objects.get(pk=request.POST['comm_pk'])
        files = comm.files.all()
        for file_ in files:
            file_.delete()
        comm.delete()
        messages.success(request, 'The communication was deleted.')
    except (KeyError, FOIACommunication.DoesNotExist):
        messages.error(request, 'The communication does not exist.')
    return redirect(next_)

@user_passes_test(lambda u: u.is_staff)
def resend_comm(request, next_):
    """Resend the FOI Communication"""
    try:
        comm = FOIACommunication.objects.get(pk=request.POST['comm_pk'])
        comm.resend(request.POST['email'])
        messages.success(request, 'The communication was resent.')
    except (KeyError, FOIACommunication.DoesNotExist):
        messages.error(request, 'The communication does not exist.')
    except (ValidationError):
        messages.error(request, 'The provided email was invalid')
    except (ValueError):
        messages.error(request, 'The communication is an orphan and cannot be resent.')
    return redirect(next_)

@user_passes_test(lambda u: u.is_staff)
def raw(request, idx):
    """Get the raw email for a communication"""
    # pylint: disable=unused-argument
    comm = get_object_or_404(FOIACommunication, pk=idx)
    if not comm.rawemail:
        raise Http404()
    return HttpResponse(comm.rawemail.raw_email, content_type='text/plain')
