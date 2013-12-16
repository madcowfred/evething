EVEthing.skillplan = {
    // current skill popover displayed
    current_popover_id: false,
    ajax: false,
        
    addSkillInPlanUrl: "",
    addRemapInPlanUrl: "",
    skillPlanEntriesJsonUrl: "",
    reorderEntriesUrl: "",
    deleteEntryUrl: "",
    cleanSkillplanUrl: "",
    optimizeSkillplanRemapsUrl: "",
    
    loadSpinner : '<i id="spin" class="icon-spinner icon-spin"></i>',
    
    levelToRoman: {0:'', 1:'I', 2:'II', 3:'III', 4:'IV', 5:'V'},
    
    remapEntry  : '<tr class="c skill_entry_handler" data-position="##position##" data-id="##id##">\n'
                + '   <td></td>\n'
                + '   <td class="l skill_entry_handler" colspan="6">\n'
                + '       <i class="icon-user"></i> Remap to \n'
                + '       <strong>##int##</strong> Int /\n'
                + '       <strong>##mem##</strong> Mem /\n'
                + '       <strong>##per##</strong> Per /\n'
                + '       <strong>##wil##</strong> Wil /\n'
                + '       <strong>##cha##</strong> Cha\n'
                + '       <span class="pull-right small"><strong>Total remap time</strong>: ##duration##</span>\n'
                + '   </td>\n'                      
                + '   <td><a href="#" class="remove-entry" data-id="##id##"><i class="icon-remove"></i></a></td>\n'
                + '</tr>\n',

    skillEntry : '<tr class="c skill_entry_handler" data-position="##position##" data-id="##id##" data-skill-id="##skill_id##" data-level="##skill_level##">\n'
               + '    <td class="sp-trained">\n'
               + '        <i class="##icon##"></i>'
               + '    </td>\n'
               + '    <td class="l  ##skill_highlight##">\n'
               + '        ##skill##'
               + '    </td>\n'
               + '    <td class="sp-group">##skill_group##</td>\n'
               + '    <td class="sp-small">##skill_primary##</td>\n'
               + '    <td class="sp-small">##skill_secondary##</td>\n'
               + '    <td class="sp-small">##skill_spph##</td>\n'
               + '    <td class="r sp-time">##skill_remaining##</td>\n'                          
               + '   <td><a href="#" class="remove-entry" data-id="##id##"><i class="icon-remove"></i></a></td>\n'
               + '</tr>\n',
                  
    onload: function() {
        $('#apply_filter').on('click',
            function(e){
                EVEthing.skillplan.reloadEntries();
                e.preventDefault();
            }
        );        
        
        $('#add_remap').on('click',
            function(e) {
                EVEthing.skillplan.addRemapPoint();
                e.preventDefault();
            }
        );       
                
        $('#optimize_remap').on('click',
            function(e) {
                EVEthing.skillplan.optimizeRemaps();
                e.preventDefault();
            }
        );       
        
        $('#searchSkill').on('keyup',EVEthing.skillplan.searchSkill);
        $('#clean_skillplan').on('click',
            function(e) {
                var confirmDelete = confirm("Are you sure you want to remove all entries from this skillplan ?")
                if(confirmDelete) {
                    EVEthing.skillplan.cleanSkillPlan();
                }
                e.preventDefault();
            }
        );
        
        // hover thing for skill descriptions
        $('.skill-list-hover').popover({ 
            animation: false, 
            trigger: 'click', 
            html: true,
            placement: 'left',
            container: 'body'
        }).on('click', 
            function(e) {
                var skill_id         = $(this).attr('data-id');
                var skill_planned_to = $(this).attr('data-plan-to-level');

                // popover on click, but only display one popover.
                if(EVEthing.skillplan.current_popover_id) {
                    if(EVEthing.skillplan.current_popover_id != $(this).attr('id')) {
                        $('#'+EVEthing.skillplan.current_popover_id).popover('hide');
                    }
                }
                EVEthing.skillplan.current_popover_id=$(this).attr('id');
                
                // define click events on button in the popover        
                $('.btn-plan-skill').on('click',
                    function() {
                        var plan_to_level   = $(this).attr('data-level');
                        var plan_skill_id   = $(this).attr('data-id');
                        EVEthing.skillplan.addSkillInPlan(plan_skill_id, plan_to_level);
                        return false;
                    }
                );
                
                $('.btn-plan-skill[data-id=' + skill_id + ']').filter(
                    function(index) {   
                        return $(this).attr('data-level') <= skill_planned_to;
                    }
                ).attr('disabled',true);
                
                e.preventDefault();
            }
        );
        EVEthing.skillplan.reloadEntries()
    },
    
    reloadEntries: function() {
        if(EVEthing.skillplan.ajax) {
            return;
        }
        // call a page with a $.get to grab the skillplan entries.
        
        var implants     = $('#implants').val();
        var character_id = Math.max($('#characters').val(), 0);
        var show_trained = ($('#show_trained').is(':checked')) ? 1 : 0;
        var url          = EVEthing.skillplan.skillPlanEntriesJsonUrl.replace('88888888888', character_id)
                                                                     .replace('77777777777', implants)
                                                                     .replace('66666666666', show_trained)

        EVEthing.skillplan.ajax = true;
        $('#skillplan-tab .active a').append(EVEthing.skillplan.loadSpinner);
        $.ajax({
            crossDomain: false,
            url: url,
            dataType: "json",
            type:'post',
            beforeSend: function(xhr, settings) {
                xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
            },
            success: function(json) {
                $('#spin').remove();
                EVEthing.skillplan.ajax = false;
                EVEthing.skillplan.parseJsonEntries(json);
            },
            error: function(xhr, status, error) {
                $('#spin').remove();
                EVEthing.skillplan.ajax = false;
                alert("Error : cannot load entries");
            }
        });

    },

    parseJsonEntries: function(json) {
        if(json.entries.length == 0) {
            $('#skillplan > tbody').html('<tr><td></td><td colspan="8">This skill plan is empty.</td></tr>');
            $('#skillplan > tfoot').html('');
            return;
        }
        footer='<tr><td></td><td colspan=7" class="r"><strong>Total time remaining</strong>: ##duration##</td></tr>';
        
        duration=EVEthing.util.durationToString(json.remaining_duration);
        if(json.remaining_duration != json.total_duration) {
            duration += ' <span class="muted">(<strong>Total:</strong> '+ EVEthing.util.durationToString(json.total_duration) +')</span>';
        }
        
        $('#skillplan > tfoot').html(footer.replace(/##duration##/,duration));
        
        // set all planned level to 0 in the skill tree
        $('.skill-list-hover').attr('data-plan-to-level', 0);        
        
        entries = "";
        cumulative_skill_time = 0;
        for(var i=0, size=json.entries.length; i < size; i++) {
            entry = json.entries[i];
            
            if(entry.remap != null) {
                duration=EVEthing.util.durationToString(entry.remap.duration);
                if(entry.remap.duration != entry.remap.total_duration) {
                    duration += ' <span class="muted">(<strong>Total:</strong> ' + EVEthing.util.durationToString(entry.remap.total_duration) +')</span>';
                }

                entries += EVEthing.skillplan.remapEntry.replace(/##position##/g    ,entry.position)
                                                        .replace(/##id##/g          ,entry.id)
                                                        .replace(/##int##/g         ,entry.remap.int)
                                                        .replace(/##mem##/g         ,entry.remap.mem)
                                                        .replace(/##per##/g         ,entry.remap.per)
                                                        .replace(/##wil##/g         ,entry.remap.wil)
                                                        .replace(/##cha##/g         ,entry.remap.cha)
                                                        .replace(/##duration##/g    ,duration)
            } else {
          
                skillName = entry.skill.name + " " + EVEthing.skillplan.levelToRoman[entry.skill.level];
                
                highlight = "";
                if (entry.skill.training) {
                    statusIcon = "icon-spinner";
                    skillName += " (Trained: " + entry.skill.percent_trained + "%)";
                    highlight = 'highlight_training';
                } else if (entry.skill.percent_trained == 100) {
                    statusIcon = "icon-ok pos"
                } else if (entry.skill.percent_trained == 0) {
                    statusIcon = "icon-remove neg"
                } else {
                    statusIcon = "icon-star-half-empty"
                    skillName += " (Trained: " + entry.skill.percent_trained + "%)";
                    highlight = 'highlight_partial';
                }
                
                cumulative_skill_time += entry.skill.remaining_time;
                entries += EVEthing.skillplan.skillEntry.replace(/##position##/g              ,entry.position)
                                                        .replace(/##id##/g                    ,entry.id)
                                                        .replace(/##skill_id##/g              ,entry.skill.id)
                                                        .replace(/##skill_level##/g           ,entry.skill.level)
                                                        .replace(/##icon##/g                  ,statusIcon)
                                                        .replace(/##skill_highlight##/g       ,highlight)
                                                        .replace(/##skill##/g                 ,skillName)
                                                        .replace(/##skill_group##/g           ,entry.skill.group)
                                                        .replace(/##skill_primary##/g         ,entry.skill.primary)
                                                        .replace(/##skill_secondary##/g       ,entry.skill.secondary)
                                                        .replace(/##skill_spph##/g            ,entry.skill.spph)
                                                        .replace(/##skill_remaining##/g       ,EVEthing.util.durationToString(entry.skill.remaining_time))
                                                        .replace(/##skill_time_cumulative##/g ,EVEthing.util.durationToString(cumulative_skill_time));
                
                // set the planned level for the current skill 
                $('#skill-list-hover-' + entry.skill.id).attr('data-plan-to-level', entry.skill.level);      
            }
        }
        $('#skillplan > tbody').html(entries);
               
        EVEthing.skillplan.bindEntriesEvents();
    },
    
    bindEntriesEvents: function() {
        // we need to reset bindings in the loaded page
        $('.skill-hover').popover({ animation: false, trigger: 'hover', html: true });
        $('.tooltips').tooltip();
        
        // init the delete bind
        $('.remove-entry').on('click',
            function(e) {
                var confirmDelete = confirm("Are you sure you want to delete this entry?\nNote: All entries depending on that skill will be deleted in the process.")
                if(confirmDelete) {
                    EVEthing.skillplan.deleteEntry($(this).attr('data-id'));
                }
                e.preventDefault();
            }
        );
                    
        // create the sortable bind
        $('#skillplan tbody').sortable({
            axis: "y",
            containment: "#skillplan" ,
            cursor: "move",
            //handle: ".skill_entry_handler",
            helper: function(e, tr)
            {
                var $originals = tr.children();
                var $helper = tr.clone();
                $helper.children().each(function(index)
                {
                    // Set helper cell sizes to match the original sizes
                    $(this).width($originals.eq(index).width());
                });
                return $helper;
            },
            start: function(event, ui) {    
                EVEthing.skillplan.previous_entries_number = ui.item.prevAll().length;
            },
            stop: function(event, ui) {
                // if we have the same number of previous entries, it's like we didn't move the entry
                if(ui.item.prevAll().length != EVEthing.skillplan.previous_entries_number) {
                                           
                    // what is the new position ?
                    var new_position = 0;
                    
                    if(ui.item.prev().length != 0) {
                        if(parseInt(ui.item.prev().attr('data-position')) < parseInt(ui.item.attr('data-position'))) {
                            new_position = ui.item.next().attr('data-position');
                        } else {
                            new_position = ui.item.prev().attr('data-position');
                        }
                    }
                    
                    EVEthing.skillplan.reorderEntry(ui.item.attr('data-id'), new_position);                    
                }
            }
        });
    },
    
    addRemapPoint: function() {
        if(EVEthing.skillplan.addRemapInPlanUrl == "") {
            alert('Add Remap URL is not set');
            return;
        }
        EVEthing.skillplan.simpleAjaxCall(EVEthing.skillplan.addRemapInPlanUrl, {}); 
    },
    
    cleanSkillPlan: function() {
        if(EVEthing.skillplan.cleanSkillplanUrl == "") {
            alert('Clean SkillPlan URL is not set');
            return;
        }
        EVEthing.skillplan.simpleAjaxCall(EVEthing.skillplan.cleanSkillplanUrl); 
    },
    
    deleteEntry: function(entry_id) {
        if(EVEthing.skillplan.deleteEntryUrl == "") {
            alert('Delete entry URL is not set');
            return;
        }
        var data = {entry_id:entry_id};        
        EVEthing.skillplan.simpleAjaxCall(EVEthing.skillplan.deleteEntryUrl, data); 
    },
    
    addSkillInPlan: function(skill_id, level) {

        if(EVEthing.skillplan.addSkillInPlanUrl == "") {
            alert('Add Skill URL is not set');
            return;
        }
        
        if(EVEthing.skillplan.ajax) {
            return;
        }
        
        // need to do the full ajax, since we need to manage the popover :(
        EVEthing.skillplan.ajax = true;
        $('#skillplan-tab .active a').append(EVEthing.skillplan.loadSpinner);
        $.ajax({
            crossDomain: false,
            url: EVEthing.skillplan.addSkillInPlanUrl,
            data: { skill_id:skill_id
                  , skill_level:level},
            type:'post',
            beforeSend: function(xhr, settings) {
                xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
            },
            success: function(json) {
                $('#spin').remove();
                EVEthing.skillplan.ajax = false;
                var response = $.parseJSON(json);
                if(response.status == "ok"){
                    $('#'+EVEthing.skillplan.current_popover_id).popover('hide');
                    EVEthing.skillplan.reloadEntries();
                }
                
            },
            error: function(xhr, status, error) {
                $('#spin').remove();
                EVEthing.skillplan.ajax = false;
                alert("Error " + xhr.status + ": " +xhr.responseText)
            }
        });
    },
   
    reorderEntry: function(entry, new_position) {
        if(EVEthing.skillplan.reorderEntriesUrl == "") {
            alert('Reorder Skill URL is not set');
            return;
        }
        var data = { entry_id:entry
                   , new_position:new_position};
                   
        EVEthing.skillplan.simpleAjaxCall(EVEthing.skillplan.reorderEntriesUrl, data, true); 
    },
        
    optimizeRemaps: function() {
        if(EVEthing.skillplan.optimizeSkillplanRemapsUrl == "") {
            alert('Optimize remaps URL is not set');
            return;
        }
        EVEthing.skillplan.simpleAjaxCall(EVEthing.skillplan.optimizeSkillplanRemapsUrl, {})
    },

    simpleAjaxCall: function(url, data, reloadIfError) {    
        reloadIfError = (typeof reloadIfError === 'undefined') ? false : reloadIfError;
        
        if(EVEthing.skillplan.ajax) {
            return;
        }
        
        EVEthing.skillplan.ajax = true;
        $('#skillplan-tab .active a').append(EVEthing.skillplan.loadSpinner);
        $.ajax({
            crossDomain: false,
            url: url,
            data: data,
            type:'post',
            beforeSend: function(xhr, settings) {
                xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
            },
            success: function(json) {
                $('#spin').remove();
                EVEthing.skillplan.ajax = false;
                response = $.parseJSON(json);
                if(response.status == "ok"){
                    EVEthing.skillplan.reloadEntries();
                }
            },
            error: function(xhr, status, error) {
                $('#spin').remove();
                EVEthing.skillplan.ajax = false;
                alert("Error " + xhr.status + ": " +xhr.responseText)
                if(reloadIfError) {
                    EVEthing.skillplan.reloadEntries();
                }
            }
        });
    },
    
    searchSkill: function() {
        var text = $('#searchSkill').val().toLowerCase();
        $('#skill_list ul').each(
            function() {
                var found = false;
                $(this).css('display','none');
                var children = $(this).find('.nav-header').attr('data-target');
                
                $(this).find(children).each(
                    function() {
                        if($(this).attr('data-name').toLowerCase().indexOf(text) >= 0) {
                            found = true;
                            $(this).addClass('in').css('height','auto');
                        } else {
                            $(this).removeClass('in').css('height','0px');
                        }
                    }
                );
                
                
                if(found || text.length == 0) {
                    $(this).css('display','');
                    
                    if(text.length == 0) {
                        $(this).find(children).removeClass('in').css('height','0px');
                    }
                }
            }
        );
    },
    

}
