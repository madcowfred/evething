import gzip

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

from core.util import get_minimum_keyid
from thing.forms import UploadSkillPlanForm
from thing.models import *
from thing.stuff import *


# ---------------------------------------------------------------------------
# List all skillplans
@login_required
def skillplan(request):
    return render_page(
        'thing/skillplan.html',
        {
            'skillplans': SkillPlan.objects.filter(user=request.user).order_by('id'),
            'visibilities': SkillPlan.VISIBILITY_CHOICES,
        },
        request,
    )


# ---------------------------------------------------------------------------
# Create a skillplan
@login_required
def skillplan_create(request):
    skill_list          = OrderedDict()
    current_market_group= None

    skills = Skill.objects.filter(item__market_group__isnull=False)
    skills = skills.select_related('item__market_group')
    skills = skills.order_by('item__market_group__name', 'item__name')

    for skill in skills:
        market_group = skill.item.market_group
        if market_group != current_market_group:
            current_market_group             = current_market_group
            skill_list[current_market_group] = []

        # TODO : add char skill level for plan creation
        # maybe create a liste with "allowed skill"
        # and "not reached prerequisite" skills
        skill_list[current_market_group].append(skill)

    
    return render_page(
        'thing/skillplan_create.html',
        {
            'skill_list': skill_list,
        },
        request,
    )
     
# ---------------------------------------------------------------------------
# Import a skillplan
@login_required
def skillplan_import_emp(request):
    if request.method == 'POST':
        form = UploadSkillPlanForm(request.POST, request.FILES)
        if form.is_valid():
            _handle_skillplan_upload(request)
            return redirect('thing.views.skillplan')
        else:
            request.session['message_type'] = 'error'
            request.session['message'] = 'Form validation failed!'
    else:
        request.session['message_type'] = 'error'
        request.session['message'] = "That doesn't look like a POST request!"

    return redirect('thing.views.skillplan')

# ---------------------------------------------------------------------------
# Create a skillplan
def skillplan_add(request):
    return

# ---------------------------------------------------------------------------
# Delete a skillplan
@login_required
def skillplan_delete(request):
    skillplan_id = request.POST.get('skillplan_id', '')
    if skillplan_id.isdigit():
        try:
            skillplan = SkillPlan.objects.get(user=request.user, id=skillplan_id)
        
        except SkillPlan.DoesNotExist:
            request.session['message_type'] = 'error'
            request.session['message'] = 'You do not own that skill plan!'
        
        else:
            request.session['message_type'] = 'success'
            request.session['message'] = 'Skill plan "%s" deleted successfully!' % (skillplan.name)
            
            # Delete all of the random things for this skillplan
            entries = SPEntry.objects.filter(skill_plan=skillplan)
            SPRemap.objects.filter(pk__in=[e.sp_remap_id for e in entries if e.sp_remap_id]).delete()
            SPSkill.objects.filter(pk__in=[e.sp_skill_id for e in entries if e.sp_skill_id]).delete()
            entries.delete()
            skillplan.delete()

    else:
        request.session['message_type'] = 'error'
        request.session['message'] = 'You seem to be doing silly things, stop that.'

    return redirect('thing.views.skillplan')


# ---------------------------------------------------------------------------
# Edit a skillplan
@login_required
def skillplan_edit(request):
    skillplan_id = request.POST.get('skillplan_id', '')
    if skillplan_id.isdigit():
        try:
            skillplan = SkillPlan.objects.get(user=request.user, id=skillplan_id)
        
        except SkillPlan.DoesNotExist:
            request.session['message_type'] = 'error'
            request.session['message'] = 'You do not own that skill plan!'
        
        else:
            skillplan.name = request.POST['name']
            skillplan.visibility = request.POST['visibility']
            skillplan.save()

            request.session['message_type'] = 'success'
            request.session['message'] = 'Skill plan "%s" edited successfully!' % (skillplan.name)

    else:
        request.session['message_type'] = 'error'
        request.session['message'] = 'You seem to be doing silly things, stop that.'

    return redirect('thing.views.skillplan')

# ---------------------------------------------------------------------------

def _handle_skillplan_upload(request):
    name = request.POST['name'].strip()
    uf = request.FILES['file']
    visibility = request.POST['visibility']

    # Check that this name is unique for the user
    if SkillPlan.objects.filter(user=request.user, name=name).count() > 0:
        request.session['message_type'] = 'error'
        request.session['message'] = "You already have a skill plan with that name!"
        return

    # Check file size, 10KB should be more than large enough
    if uf.size > 10240:
        request.session['message_type'] = 'error'
        request.session['message'] = "That file is too large!"
        return

    data = StringIO(uf.read())

    # Try opening it as a gzip file
    gf = gzip.GzipFile(fileobj=data)
    try:
        data = gf.read()
    except IOError:
        request.session['message_type'] = 'error'
        request.session['message'] = "That doesn't look like a .EMP file!"
        return

    # Make sure it's valid XML
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        request.session['message_type'] = 'error'
        request.session['message'] = "That doesn't look like a .EMP file!"
        return

    # FINALLY
    skillplan = SkillPlan.objects.create(
        user=request.user,
        name=name,
        visibility=visibility,
    )
    
    _parse_emp_plan(skillplan, root)

    request.session['message_type'] = 'success'
    request.session['message'] = "Skill plan uploaded successfully."


def _parse_emp_plan(skillplan, root):
    entries = []
    position = 0
    for entry in root.findall('entry'):
        # Create the various objects for the remapping if it exists
        remapping = entry.find('remapping')
        if remapping is not None:
            # <remapping status="UpToDate" per="17" int="27" mem="21" wil="17" cha="17" description="" />
            spr = SPRemap.objects.create(
                int_stat=remapping.attrib['int'],
                mem_stat=remapping.attrib['mem'],
                per_stat=remapping.attrib['per'],
                wil_stat=remapping.attrib['wil'],
                cha_stat=remapping.attrib['cha'],
            )

            entries.append(SPEntry(
                skill_plan=skillplan,
                position=position,
                sp_remap=spr,
            ))

            position += 1

        # Create the various objects for the skill
        try:
            sps = SPSkill.objects.create(
                skill_id=entry.attrib['skillID'],
                level=entry.attrib['level'],
                priority=entry.attrib['priority'],
            )
        except:
            continue
            
        entries.append(SPEntry(
            skill_plan=skillplan,
            position=position,
            sp_skill=sps,
        ))

        position += 1

    SPEntry.objects.bulk_create(entries)
