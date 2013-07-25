import gzip
import json

from django.http import HttpResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.shortcuts import redirect, get_object_or_404
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET
    
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
def skillplan_edit(request, skillplan_id):

    if skillplan_id.isdigit():
        skillplan = get_object_or_404(SkillPlan, user=request.user, pk=skillplan_id)
                

        # Init the global skill list
        skill_list           = OrderedDict()
        current_market_group = None

        skills = Skill.objects.filter(item__market_group__isnull=False)
        skills = skills.select_related('item__market_group')
        skills = skills.order_by('item__market_group__name', 'item__name')
        
        for skill in skills:
            market_group = skill.item.market_group
            if market_group != current_market_group:
                current_market_group = market_group
                skill_list[current_market_group] = []

            # TODO : add char skill level for plan creation
            # maybe create a list with "allowed skill"
            # and "not reached prerequisite" skills
            
            skill_list[current_market_group].append(skill)
        
        characters = Character.objects.filter(
            apikeys__user=request.user,
        ).select_related(
            'config',
            'details',
        ).distinct()

        try:
            selected_char = characters.get(id=request.GET.get('character'))
        except Character.DoesNotExist:
            selected_char = False
        
        implants = request.GET.get('implants', '')
        if implants.isdigit() and 0 <= int(implants) <= 5:
            implants = int(implants)
        else:
            implants = 0

        return render_page(
            'thing/skillplan_details.html',
            {   
                'skillplan'         : skillplan,
                'skill_list'        : skill_list,
                'show_trained'      : ('show_trained' in request.GET),
                'implants'          : implants,
                'characters'        : characters,
                'selected_character': selected_char
            },
            request,
        )

    else:
        redirect('thing.views.skillplan')

# ---------------------------------------------------------------------------
# 
@login_required
def skillplan_render_entries(request, skillplan_id, character_id, implants, show_trained):
    skillplan = get_object_or_404(SkillPlan, user=request.user, pk=skillplan_id)
    
    try:
        character = Character.objects.get(apikeys__user=request.user, id=character_id).select_related('config','details')
    except Character.DoesNotExist:
        character = False
    
    if implants.isdigit() and 0 <= int(implants) <= 5:
        implants = int(implants)
    else:
        implants = 0 
    
    show_trained=bool(show_trained)
    
    return _skillplan_list(request, skillplan, character, implants, show_trained)
        
# ---------------------------------------------------------------------------
# Add a given skill & prerequisites
@login_required
def skillplan_add_skill(request):
    """
    Add a skill and all of it's prerequisite (not already in the plan)
    into the skill plan
    
    This function will return a json with status "ok" or a http error code.
    
    POST:   skillplan_id : id of the plan
            skill_id : skill to add 
            skill_level : the level of the skill to add
    """
    tt = TimerThing('skill_add_skill')

    tt.add_time('init')
    
    if request.is_ajax():
        skill_id        = request.POST.get('skill_id', '')
        skillplan_id    = request.POST.get('skillplan_id', '')
        skill_level     = request.POST.get('skill_level', '')
        
        if not skill_level.isdigit() or int(skill_level) < 1 or int(skill_level) > 5:
            skill_level = 1
        skill_level = int(skill_level)
        
        if skill_id.isdigit() and skillplan_id.isdigit():
            try:
                skillplan = SkillPlan.objects.get(user=request.user, id=skillplan_id)
                skill = Skill.objects.get(item__id=skill_id)
                
            except Skill.DoesNotExist:
                return HttpResponse(content='That skill does not exist', status=500) 
                
            except SkillPlan.DoesNotExist:
                return HttpResponse(content='That skillplan does not exist', status=500)     

            skill_list = OrderedDict()
            skills_in_plan = {}
            last_position = 0
            
            tt.add_time('Get objects')
            
            # get the list of all skills already in the plan
            for entry in skillplan.entries.select_related('sp_remap', 'sp_skill__skill__item'):         
                if entry.sp_remap is not None:
                    continue
                if entry.sp_skill is not None:
                    skills_in_plan[entry.sp_skill.skill.item.id] = entry.sp_skill.level
                last_position = entry.position + 1
                
            tt.add_time('Get skillplan entries')
            
            # if the skill is not already in the plan at the same level, we'll try to add it.
            if (skill_id in skills_in_plan and skill_level > skills_in_plan[skill_id]) or skill_id not in skills_in_plan:
            
                # fetch all prerequisites
                _get_skill_prerequisites(skill, skill_list, skills_in_plan)
                
                tt.add_time('Get skills prerequisites')
                
                if skill_id in skills_in_plan:
                    start_level = skills_in_plan[skill_id]
                else: 
                    start_level = 1
                
                
                # add the skill (we want to add) to the list
                for level in range(start_level, skill_level+1):
                    skill_list[len(skill_list)] = {'id':skill_id, 'level':level}
            
            # if we have any new skill to add, just create the new entries :)
            entries = []
            
            for index, skill_to_add in skill_list.items():
                try:
                    sps = SPSkill.objects.create(
                        skill_id=skill_to_add['id'],
                        level=skill_to_add['level'],
                        priority=2,
                    )
                except:
                    continue
            
                entries.append(SPEntry(
                    skill_plan=skillplan,
                    position=last_position,
                    sp_skill=sps,
                ))

                last_position += 1
                
            print(entries)
            SPEntry.objects.bulk_create(entries)
            
            tt.add_time('Skill Entries creation')
            if settings.DEBUG:
                tt.finished()    
                
            return HttpResponse(json.dumps({'status':'ok'}), status=200)
        
        else:
            return HttpResponse(content='Cannot add the skill : no skill or no skillplan provided', status=500)       
    else:
        return HttpResponse(content='Cannot call this page directly', status=403)

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
@login_required
def skillplan_create(request):

    skillplan = SkillPlan.objects.create(
        user=request.user,
        name=request.POST['name'],
        visibility=request.POST['visibility'],
    )
    
    skillplan.save()
    
    return redirect('thing.views.skillplan')
    
# ---------------------------------------------------------------------------
# Export Skillplan
@login_required
def skillplan_export(request, skillplan_id):
    # path = os.expanduser('~/files/pdf/')
    # f = open(path+filename, "r")
    # response = HttpResponse(FileWrapper(f), content_type='application/x-gzip')
    # response ['Content-Disposition'] = 'attachment; filename=yourFile.emp'
    # f.close()
    return response

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
def skillplan_info_edit(request):
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
# Return the entries of a given skillplan
def _skillplan_list(request, skillplan, character, implants, show_trained):
    tt = TimerThing('skillplan_list_entries')

    utcnow = datetime.datetime.utcnow()

    tt.add_time('init')

    # Init some stuff to have no errors
    learned = {}
    training_skill = None
    # Try retrieving learned data from cache
    if character:
        cache_key = 'character_skillplan:learned:%s' % (character.id)
        learned = cache.get(cache_key)
        # Not cached, fetch from database and cache
        if learned is None:
            learned = {}
            for cs in CharacterSkill.objects.filter(character=character).select_related('skill__item'):
                learned[cs.skill.item.id] = cs
            cache.set(cache_key, learned, 300)
    
        tt.add_time('char skills')
    
        # Possibly get training information
        training_skill = None
        if character.config.show_skill_queue is True:
            sqs = list(SkillQueue.objects.select_related('skill__item').filter(character=character, end_time__gte=utcnow))
            if sqs:
                training_skill = sqs[0]
    
        tt.add_time('training')
        
    # Initialise stat stuff
    if character and character.details:
        remap_stats = dict(
            int_attribute=character.details.int_attribute,
            mem_attribute=character.details.mem_attribute,
            per_attribute=character.details.per_attribute,
            wil_attribute=character.details.wil_attribute,
            cha_attribute=character.details.cha_attribute,
        )
        
    else:
        # default stats on a new char
        # no char will ever have 0 to any attribute
        remap_stats = dict(
            int_attribute=20,
            mem_attribute=20,
            per_attribute=20,
            wil_attribute=20,
            cha_attribute=19,
        )

    implant_stats = {}
    for stat in ('int', 'mem', 'per', 'wil', 'cha'):
        k = '%s_bonus' % (stat)
        if implants == 0 and character:
            implant_stats[k] = getattr(character.details, k, 0)
        else:
            implant_stats[k] = implants

    # Iterate over all entries in this skill plan
    entries = []
    total_remaining = 0.0
    for entry in skillplan.entries.select_related('sp_remap', 'sp_skill__skill__item__item_group'):
        # It's a remap entry
        if entry.sp_remap is not None:
        
            # If the remap have every attributes set to 0, we do not add it.
            # (happen when remap are not set on evemon before exporting .emp
            if entry.sp_remap.int_stat == 0 and entry.sp_remap.mem_stat == 0 and entry.sp_remap.per_stat == 0 and entry.sp_remap.wil_stat == 0 and entry.sp_remap.cha_stat == 0:
               continue
                
            
            # Delete the previous remap if it's two in a row, that makes no sense
            if entries and entries[-1].sp_remap is not None:
                entries.pop()


            remap_stats['int_attribute'] = entry.sp_remap.int_stat
            remap_stats['mem_attribute'] = entry.sp_remap.mem_stat
            remap_stats['per_attribute'] = entry.sp_remap.per_stat
            remap_stats['wil_attribute'] = entry.sp_remap.wil_stat
            remap_stats['cha_attribute'] = entry.sp_remap.cha_stat

        # It's a skill entry
        if entry.sp_skill is not None:
            skill = entry.sp_skill.skill
            
            # If this skill is already learned
            cs = learned.get(skill.item.id, None)
            if cs is not None:
                # Mark it as injected if level 0
                if cs.level == 0:
                    entry.z_injected = True
                # It might already be trained
                elif cs.level >= entry.sp_skill.level:
                    # If we don't care about trained skills, skip this skill entirely
                    if not show_trained:
                        continue

                    entry.z_trained = True
            # Not learned, need to buy it
            else:
                entry.z_buy = True

            # Calculate SP/hr
            if remap_stats:
                entry.z_sppm = skill.get_sppm_stats(remap_stats, implant_stats)
            else:
                entry.z_sppm = skill.get_sp_per_minute(character)
            
            # 0 sppm is bad
            entry.z_sppm = max(1, entry.z_sppm)
            entry.z_spph = int(entry.z_sppm * 60)

            # Calculate time remaining
            if training_skill is not None and training_skill.skill_id == entry.sp_skill.skill_id and training_skill.to_level == entry.sp_skill.level:
                entry.z_remaining = total_seconds(training_skill.end_time - utcnow)
                entry.z_training = True
            else:
                entry.z_remaining = (skill.get_sp_at_level(entry.sp_skill.level) - skill.get_sp_at_level(entry.sp_skill.level - 1)) / entry.z_sppm * 60

            # Add time remaining to total
            if not hasattr(entry, 'z_trained'):
                total_remaining += entry.z_remaining

        entries.append(entry)

    tt.add_time('skillplan loop')
    if settings.DEBUG:
        tt.finished()

    return render_page(
        'thing/skillplan_entries.html',
        {   
            'show_trained': show_trained,
            'implants': implants,
            'char': character,
            'entries': entries,
            'total_remaining': total_remaining,
        },
        request,
    )
    
# ---------------------------------------------------------------------------
# Handle the upload of a .EMP skillplan 
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

# ---------------------------------------------------------------------------
# Parse an emp skillplan and save it into the database
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

# ---------------------------------------------------------------------------
# Return a dict with all the prerequisite of a given skill
def _get_skill_prerequisites(skill, skill_list, skills_in_plan):
    
    parents = skill.get_skill_parent()
    if parents is None:
        return
        
    for parent in parents:
        
        _get_skill_prerequisites(parent.parent_skill, skill_list, skills_in_plan)
        
        # check to what level we already added the skill, and update it 
        if parent.parent_skill.item.id in skills_in_plan:
            skill_start_level = skills_in_plan[parent.parent_skill.item.id]
            if skills_in_plan[parent.parent_skill.item.id] < parent.level:
                skills_in_plan[parent.parent_skill.item.id] = parent.level
            
            # we do not need to re-add the skill, since we already added it into the list
            if parent.level == skill_start_level:
                continue
        else:
            skill_start_level = 1
            skills_in_plan[parent.parent_skill.item.id] = parent.level
        
        # add all level of the skill needed
        for level in range(skill_start_level, parent.level+1):
            skill_list[len(skill_list)] = {'id':parent.parent_skill.item.id, 'level':level}
    return
