EVEthing.skillplan = {
    // current skill popover displayed
    current_popover_id: false,
    
    skillplanId: 0,
    addSkillInPlanUrl: "",
    addRemapInPlanUrl: "",
    skillPlanEntriesUrl: "",
    reorderEntriesUrl: "",
    
    onload: function() {
        $('#apply_filter').click(
            function(){
                EVEthing.skillplan.reloadEntries();
                return false;
            }
        );        
        
        $('#add_remap').click(
            function() {
                EVEthing.skillplan.addRemapPoint();
                return false;
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
            function() {
            
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
                
                return false;
            }
        );
        EVEthing.skillplan.reloadEntries()
    },
    
    addRemapPoint: function() {
        $.ajax({
            crossDomain: false,
            url: EVEthing.skillplan.addRemapInPlanUrl,
            data: { skillplan_id:EVEthing.skillplan.skillplanId },
            type:'post',
            beforeSend: function(xhr, settings) {
                xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
            },
            success: function(json) {
                response = $.parseJSON(json);
                if(response.status == "ok"){
                    EVEthing.skillplan.reloadEntries();
                }
            },
            error: function(xhr, status, error) {
                // TODO : 
                // display the error for the user (at least !)
            }
        });

    },
    
    addSkillInPlan: function(skill_id, level) {
        $.ajax({
            crossDomain: false,
            url: EVEthing.skillplan.addSkillInPlanUrl,
            data: { skill_id:skill_id
                  , skill_level:level
                  , skillplan_id:EVEthing.skillplan.skillplanId },
            type:'post',
            beforeSend: function(xhr, settings) {
                xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
            },
            success: function(json) {
                response = $.parseJSON(json);
                if(response.status == "ok"){
                    $('#'+EVEthing.skillplan.current_popover_id).popover('hide');
                    EVEthing.skillplan.reloadEntries();
                }
            },
            error: function(xhr, status, error) {
                // TODO : 
                // display the error for the user (at least !)
            }
        });
    },
    
    reloadEntries: function() {
        // call a page with a $.get to grab the skillplan entries.
        ajax_wait = true;

        var implants     = $('#implants').val();
        var character_id = Math.max($('#characters').val(), 0);
        var show_trained = ($('#show_trained').is(':checked')) ? 1 : 0;
        var url          = EVEthing.skillplan.skillPlanEntriesUrl.replace('99999999999', EVEthing.skillplan.skillplanId)
                                                                 .replace('88888888888', character_id)
                                                                 .replace('77777777777', implants)
                                                                 .replace('66666666666', show_trained)
        
        $.get(url, function(data) {
            $('#skillplan').html(data); 
            
            
            // we need to reset the hover
            $('.skill-hover').popover({ animation: false, trigger: 'hover', html: true });
            $('#skillplan tbody').sortable({
                axis: "y",
                containment: "parent" ,
                cursor: "move",
                handle: ".skill_entry_handler",
                helper: "clone",
                start: function(event, ui) {    
                    EVEthing.skillplan.previous_entries_number = ui.item.prevAll().length;
                },
                stop: function(event, ui) {
                    // if we have the same number of previous entries, it's like we didn't move the entry
                    if(ui.item.prevAll().length != EVEthing.skillplan.previous_entries_number) {
                                               
                        // what is the new position ?
                        var new_position = 0;
                        
                        if(ui.item.prev().length != 0) {
                            if(ui.item.prev().attr('data-position') < ui.item.attr('data-position')) {
                                new_position = ui.item.next().attr('data-position');
                            } else {
                                new_position = ui.item.prev().attr('data-position');
                            }
                        }
                        
                        EVEthing.skillplan.reorderEntry(ui.item.attr('data-id'), new_position);                    
                    }
                }
            });
        })
    },
    
    reorderEntry: function(entry, new_position) {
        $.ajax({
            crossDomain: false,
            url: EVEthing.skillplan.addSkillInPlanUrl,
            data: { entry_id:entry
                  , new_position:new_position
                  , skillplan_id:EVEthing.skillplan.skillplanId },
            type:'post',
            beforeSend: function(xhr, settings) {
                xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
            },
            success: function(json) {
                response = $.parseJSON(json);
                if(response.status == "ok"){
                    EVEthing.skillplan.reloadEntries();
                }
            },
            error: function(xhr, status, error) {
                // TODO : 
                // display the error for the user (at least !)
            }
        });
    },
    
    optimizeAttributes: function() {
    
    },
    
    optimizeRemaps: function() {
    
    },

}
